"""Critic agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse


class CriticAgent(BaseAgent):
    """Fact-checks the final answer against shared-state evidence."""

    name = "critic"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient(temperature=0.0)

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.critic_notes` with fact-check and citation findings."""

        citation_coverage = _citation_coverage(state)
        response = self.llm_client.complete(
            system_prompt=(
                "<persona>\n"
                "You are the Critic agent in a multi-agent research workflow. "
                "Your job is to fact-check the Writer's final answer against the available "
                "sources, research notes, and analysis notes.\n"
                "</persona>\n\n"
                "<rules>\n"
                "- Check whether important claims are supported by the provided evidence.\n"
                "- Flag unsupported, overstated, or ambiguous claims.\n"
                "- Check whether citations match the source list.\n"
                "- Be strict but practical; do not rewrite the full answer.\n"
                "</rules>\n\n"
                "<tools_instructions>\n"
                "Use only the shared-state evidence in the user message. Do not perform new "
                "web search and do not introduce new facts.\n"
                "</tools_instructions>\n\n"
                "<response_format>\n"
                "Return sections: Verdict, Supported claims, Citation issues, "
                "Unsupported or weak claims, Suggested fixes.\n"
                "</response_format>\n\n"
                "<constraints>\n"
                "Do not invent citations. If the evidence is insufficient, say so explicitly.\n"
                "</constraints>"
            ),
            user_prompt=(
                f"User query: {state.request.query}\n"
                f"Audience: {state.request.audience}\n\n"
                f"Sources:\n{_format_sources(state.sources)}\n\n"
                f"Research notes:\n{state.research_notes or 'None'}\n\n"
                f"Analysis notes:\n{state.analysis_notes or 'None'}\n\n"
                f"Final answer to fact-check:\n{state.final_answer or 'None'}\n\n"
                f"Measured citation coverage: {citation_coverage:.0%}"
            ),
        )
        state.critic_notes = response.content
        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=response.content,
                metadata={
                    "citation_coverage": citation_coverage,
                    **_llm_metadata(response),
                },
            )
        )
        state.add_trace_event(
            "critic.completed",
            {
                "citation_coverage": citation_coverage,
                "tokens": _token_count(response),
                "cost_usd": response.cost_usd,
            },
        )
        return state


def _format_sources(sources: list[SourceDocument]) -> str:
    if not sources:
        return "No sources available."
    lines: list[str] = []
    for index, source in enumerate(sources, start=1):
        lines.append(
            f"[{index}] {source.title}\n"
            f"URL: {source.url or 'no url'}\n"
            f"Snippet: {source.snippet}"
        )
    return "\n\n".join(lines)


def _citation_coverage(state: ResearchState) -> float:
    if not state.sources or not state.final_answer:
        return 0.0
    cited = sum(
        1
        for index in range(1, len(state.sources) + 1)
        if f"[{index}]" in state.final_answer
    )
    return cited / len(state.sources)


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
