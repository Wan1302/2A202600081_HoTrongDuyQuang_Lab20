"""Multi-agent workflow orchestration."""

from time import perf_counter

from multi_agent_research_lab.agents import (
    AnalystAgent,
    CriticAgent,
    ResearcherAgent,
    SupervisorAgent,
    WriterAgent,
)
from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.errors import AgentExecutionError, LabError
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import langsmith_trace_context, trace_span


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph.

    The implementation is dependency-light and mirrors a LangGraph-style state machine:
    supervisor -> routed worker -> supervisor until done.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        supervisor: SupervisorAgent | None = None,
        researcher: ResearcherAgent | None = None,
        analyst: AnalystAgent | None = None,
        writer: WriterAgent | None = None,
        critic: CriticAgent | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.supervisor = supervisor or SupervisorAgent(self.settings)
        self.agents: dict[str, BaseAgent] = {
            "researcher": researcher or ResearcherAgent(),
            "analyst": analyst or AnalystAgent(),
            "writer": writer or WriterAgent(),
            "critic": critic or CriticAgent(),
        }

    def build(self) -> dict[str, object]:
        """Create a serializable graph description for trace/debug output."""

        return {
            "nodes": ["supervisor", "researcher", "analyst", "writer", "critic", "done"],
            "edges": [
                ("supervisor", "researcher"),
                ("supervisor", "analyst"),
                ("supervisor", "writer"),
                ("supervisor", "critic"),
                ("supervisor", "done"),
                ("researcher", "supervisor"),
                ("analyst", "supervisor"),
                ("writer", "supervisor"),
                ("critic", "supervisor"),
            ],
            "max_iterations": self.settings.max_iterations,
            "timeout_seconds": self.settings.timeout_seconds,
        }

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the graph and return final state."""

        graph = self.build()
        with langsmith_trace_context(
            settings=self.settings,
            metadata={"workflow": "multi_agent_research", "query": state.request.query},
        ), trace_span(
            "multi_agent_workflow",
            {"max_iterations": self.settings.max_iterations},
            run_type="chain",
            inputs={"query": state.request.query, "graph": graph},
            settings=self.settings,
        ) as span:
            result = self._execute(state, graph)
            span["outputs"] = _state_summary(result)
            return result

    def _execute(self, state: ResearchState, graph: dict[str, object]) -> ResearchState:
        """Run the state-machine loop inside an optional LangSmith root span."""

        state.add_trace_event("workflow.started", {"graph": graph})
        deadline = perf_counter() + self.settings.timeout_seconds

        while perf_counter() < deadline:
            with trace_span(
                "supervisor",
                {"iteration": state.iteration},
                run_type="chain",
                inputs=_supervisor_inputs(state),
                settings=self.settings,
            ) as supervisor_span:
                state = self.supervisor.run(state)
                supervisor_span["outputs"] = _supervisor_outputs(state)

            route = state.route_history[-1]
            if route == "done":
                state.add_trace_event("workflow.completed", {"reason": "supervisor_done"})
                return state

            agent = self.agents.get(route)
            if agent is None:
                raise AgentExecutionError(f"Unknown route from supervisor: {route}")

            try:
                with trace_span(
                    route,
                    {"iteration": state.iteration},
                    run_type="chain",
                    inputs=_agent_inputs(route, state),
                    settings=self.settings,
                ) as agent_span:
                    state = agent.run(state)
                    agent_span["outputs"] = _agent_outputs(route, state)
            except LabError as exc:
                state.errors.append(f"{route} failed: {exc}")
                state.add_trace_event("workflow.agent_failed", {"route": route, "error": str(exc)})
                state = self._fallback_after_failure(state, route)

        state.errors.append(f"Workflow timed out after {self.settings.timeout_seconds} seconds.")
        state.add_trace_event(
            "workflow.timeout",
            {"timeout_seconds": self.settings.timeout_seconds},
        )
        if not state.final_answer:
            state.final_answer = self._fallback_answer(state)
        return state

    def _fallback_after_failure(self, state: ResearchState, route: str) -> ResearchState:
        if route == "researcher" and not state.research_notes:
            state.research_notes = "Researcher failed; no external evidence was collected."
        if route == "analyst" and not state.analysis_notes:
            state.analysis_notes = "Analyst failed; use research notes directly."
        if route == "writer" and not state.final_answer:
            state.final_answer = self._fallback_answer(state)
        if route == "critic" and not state.critic_notes:
            state.critic_notes = "Critic failed; final answer was not fact-checked."
        return state

    def _fallback_answer(self, state: ResearchState) -> str:
        return (
            "The workflow could not complete a fully synthesized answer. "
            f"Research notes: {state.research_notes or 'missing'}\n\n"
            f"Analysis notes: {state.analysis_notes or 'missing'}"
        )


def _state_summary(state: ResearchState) -> dict[str, object]:
    return {
        "iteration": state.iteration,
        "route_history": list(state.route_history),
        "source_count": len(state.sources),
        "has_research_notes": state.research_notes is not None,
        "has_analysis_notes": state.analysis_notes is not None,
        "has_final_answer": state.final_answer is not None,
        "has_critic_notes": state.critic_notes is not None,
        "error_count": len(state.errors),
    }


def _supervisor_inputs(state: ResearchState) -> dict[str, object]:
    data = _state_summary(state)
    data.update(
        {
            "query": state.request.query,
            "research_notes": state.research_notes,
            "analysis_notes": state.analysis_notes,
            "final_answer": state.final_answer,
            "critic_notes": state.critic_notes,
            "errors": list(state.errors),
        }
    )
    return data


def _supervisor_outputs(state: ResearchState) -> dict[str, object]:
    return {
        "next_route": state.route_history[-1],
        "iteration": state.iteration,
        "route_history": list(state.route_history),
    }


def _agent_inputs(route: str, state: ResearchState) -> dict[str, object]:
    data = _state_summary(state)
    data["query"] = state.request.query

    if route == "researcher":
        data["max_sources"] = state.request.max_sources
        data["audience"] = state.request.audience
    elif route == "analyst":
        data["research_notes"] = state.research_notes
        data["sources"] = _serialized_sources(state)
    elif route == "writer":
        data["research_notes"] = state.research_notes
        data["analysis_notes"] = state.analysis_notes
        data["sources"] = _serialized_sources(state)
    elif route == "critic":
        data["research_notes"] = state.research_notes
        data["analysis_notes"] = state.analysis_notes
        data["final_answer"] = state.final_answer
        data["sources"] = _serialized_sources(state)

    return data


def _agent_outputs(route: str, state: ResearchState) -> dict[str, object]:
    data = _state_summary(state)

    if route == "researcher":
        data["research_notes"] = state.research_notes
        data["sources"] = _serialized_sources(state)
    elif route == "analyst":
        data["analysis_notes"] = state.analysis_notes
    elif route == "writer":
        data["final_answer"] = state.final_answer
    elif route == "critic":
        data["critic_notes"] = state.critic_notes

    data["errors"] = list(state.errors)
    return data


def _serialized_sources(state: ResearchState) -> list[dict[str, object]]:
    return [source.model_dump() for source in state.sources]
