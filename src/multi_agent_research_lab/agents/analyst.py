"""Analyst agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient(temperature=0.1)

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`."""

        research_notes = state.research_notes or "No research notes were collected."
        response = self.llm_client.complete(
            system_prompt=(
                "<persona>\n"
                "You are the Analyst agent in a multi-agent research workflow. "
                "Your job is to turn research notes into decision-ready insights.\n"
                "</persona>\n\n"
                "<rules>\n"
                "- Extract the central thesis and the strongest 3-5 claims.\n"
                "- Separate strong evidence from weak, missing, or uncertain evidence.\n"
                "- Identify tradeoffs, risks, and likely failure modes.\n"
                "- Keep citation markers from the research notes.\n"
                "</rules>\n\n"
                "<tools_instructions>\n"
                "Use the Researcher notes provided in shared state. Do not introduce "
                "new external facts or new citations.\n"
                "</tools_instructions>\n\n"
                "<response_format>\n"
                "Return sections: Thesis, Key claims, Tradeoffs, Risks / failure modes, "
                "Confidence level.\n"
                "</response_format>\n\n"
                "<constraints>\n"
                "Do not write the final answer. Do not remove citation markers.\n"
                "</constraints>"
            ),
            user_prompt=(
                f"Research question: {state.request.query}\n"
                f"Audience: {state.request.audience}\n\n"
                f"Research notes:\n{research_notes}\n\n"
                "Return: thesis, 3-5 key claims, tradeoffs, risks/failure modes, "
                "and confidence level."
            ),
        )
        state.analysis_notes = response.content
        state.agent_results.append(
            AgentResult(
                agent=AgentName.ANALYST,
                content=response.content,
                metadata=_llm_metadata(response),
            )
        )
        state.add_trace_event(
            "analyst.completed",
            {"tokens": _token_count(response), "cost_usd": response.cost_usd},
        )
        return state


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
