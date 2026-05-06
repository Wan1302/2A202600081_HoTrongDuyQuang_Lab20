"""Writer agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient(temperature=0.4)

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`."""

        response = self.llm_client.complete(
            system_prompt=(
                "<persona>\n"
                "You are the Writer agent in a multi-agent research workflow. "
                "Your job is to produce the final user-facing answer.\n"
                "</persona>\n\n"
                "<rules>\n"
                "- Use only the research notes, analysis notes, and source list "
                "from shared state.\n"
                "- Write for the requested audience.\n"
                "- Use numbered citations like [1] for evidence-backed claims.\n"
                "- Every substantive claim about a method, benefit, risk, tradeoff, "
                "or production recommendation must include at least one source citation.\n"
                "- If a claim is useful but not directly supported by the sources, mark it as "
                "uncertain instead of presenting it as fact.\n"
                "- Prefer several short cited claims over uncited general paragraphs.\n"
                "- Be direct, structured, and explicit about uncertainty.\n"
                "</rules>\n\n"
                "<tools_instructions>\n"
                "The Researcher and Analyst have already completed their work. Do not claim "
                "that you performed new search or verification.\n"
                "</tools_instructions>\n\n"
                "<response_format>\n"
                "Return the final answer with concise sections. Each paragraph or bullet that "
                "contains evidence-backed content should include citations such as [1] or [2]. "
                "End with a short Sources section mapping citation numbers to titles.\n"
                "</response_format>\n\n"
                "<constraints>\n"
                "Do not invent facts, URLs, or citations. Do not cite a source unless it appears "
                "in the available source list. Do not submit an answer with uncited substantive "
                "claims when sources are available.\n"
                "</constraints>"
            ),
            user_prompt=(
                f"User query: {state.request.query}\n"
                f"Audience: {state.request.audience}\n\n"
                f"Research notes:\n{state.research_notes or 'None'}\n\n"
                f"Analysis notes:\n{state.analysis_notes or 'None'}\n\n"
                f"Available sources:\n{_format_source_list(state.sources)}\n\n"
                "Write the final response. Include citations throughout the answer, not only "
                "in the Sources section. If evidence is insufficient for a claim, explicitly "
                "label it as uncertain. Include a short 'Sources' section."
            ),
        )
        state.final_answer = response.content
        state.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=response.content,
                metadata=_llm_metadata(response),
            )
        )
        state.add_trace_event(
            "writer.completed",
            {"tokens": _token_count(response), "cost_usd": response.cost_usd},
        )
        return state


def _format_source_list(sources: list[SourceDocument]) -> str:
    if not sources:
        return "No sources available."
    lines = []
    for index, source in enumerate(sources, start=1):
        lines.append(f"[{index}] {source.title}: {source.url or 'no url'}")
    return "\n".join(lines)


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
