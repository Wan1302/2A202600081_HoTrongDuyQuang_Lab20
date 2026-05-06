"""Supervisor / router implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(self, state: ResearchState) -> ResearchState:
        """Update `state.route_history` with the next route."""

        if state.iteration >= self.settings.max_iterations:
            if not state.final_answer:
                next_route = "writer"
            elif not state.critic_notes:
                next_route = "critic"
            else:
                next_route = "done"
            reason = "max_iterations_guard"
        elif state.final_answer and state.critic_notes:
            next_route = "done"
            reason = "final_answer_and_critic_present"
        elif state.final_answer:
            next_route = "critic"
            reason = "critic_missing"
        elif not state.research_notes:
            next_route = "researcher"
            reason = "research_missing"
        elif not state.analysis_notes:
            next_route = "analyst"
            reason = "analysis_missing"
        else:
            next_route = "writer"
            reason = "ready_to_write"

        state.record_route(next_route)
        state.add_trace_event(
            "supervisor.route",
            {
                "next_route": next_route,
                "reason": reason,
                "iteration": state.iteration,
                "errors": list(state.errors),
            },
        )
        state.agent_results.append(
            AgentResult(
                agent=AgentName.SUPERVISOR,
                content=next_route,
                metadata={"reason": reason, "iteration": state.iteration},
            )
        )
        return state
