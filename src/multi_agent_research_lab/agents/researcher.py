"""Researcher agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse
from multi_agent_research_lab.services.search_client import SearchClient


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        search_client: SearchClient | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient(temperature=0.2)
        self.search_client = search_client or SearchClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`."""

        sources = self.search_client.search(
            state.request.query,
            max_results=state.request.max_sources,
        )
        source_block = _format_sources(sources)
        response = self.llm_client.complete(
            system_prompt=(
                "<persona>\n"
                "You are the Researcher agent in a multi-agent research workflow. "
                "Your job is to collect evidence-backed notes for downstream agents.\n"
                "</persona>\n\n"
                "<rules>\n"
                "- Extract only claims supported by the provided sources.\n"
                "- Preserve numbered source references like [1].\n"
                "- Separate useful evidence from gaps or uncertainty.\n"
                "- Do not write the final user-facing answer.\n"
                "</rules>\n\n"
                "<tools_instructions>\n"
                "The search step has already provided the source list in the user message. "
                "Use only those sources; do not assume access to live web browsing.\n"
                "</tools_instructions>\n\n"
                "<response_format>\n"
                "Return concise research notes with these sections: Key facts, Evidence, "
                "Gaps / uncertainty.\n"
                "</response_format>\n\n"
                "<constraints>\n"
                "Do not add uncited facts. Do not optimize for style over evidence.\n"
                "</constraints>"
            ),
            user_prompt=(
                f"Research question: {state.request.query}\n"
                f"Audience: {state.request.audience}\n\n"
                f"Sources:\n{source_block}\n\n"
                "Return concise research notes with: key facts, useful evidence, and gaps."
            ),
        )
        state.sources = sources
        state.research_notes = response.content
        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=response.content,
                metadata={"source_count": len(sources), **_llm_metadata(response)},
            )
        )
        state.add_trace_event(
            "researcher.completed",
            {
                "source_count": len(sources),
                "tokens": _token_count(response),
                "cost_usd": response.cost_usd,
            },
        )
        return state


def _format_sources(sources: list[SourceDocument]) -> str:
    lines: list[str] = []
    for index, source in enumerate(sources, start=1):
        url = source.url or "no url"
        lines.append(f"[{index}] {source.title} ({url})\n{source.snippet}")
    return "\n\n".join(lines)


def _token_count(response: LLMResponse) -> int | None:
    if response.input_tokens is None or response.output_tokens is None:
        return None
    return response.input_tokens + response.output_tokens


def _llm_metadata(response: LLMResponse) -> dict[str, int | float | None]:
    return {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "total_tokens": _token_count(response),
        "cost_usd": response.cost_usd,
    }
