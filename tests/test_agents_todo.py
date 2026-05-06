from multi_agent_research_lab.agents import (
    AnalystAgent,
    CriticAgent,
    ResearcherAgent,
    SupervisorAgent,
    WriterAgent,
)
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse


class FakeLLMClient(LLMClient):
    def __init__(self) -> None:
        pass

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        return LLMResponse(
            content=f"fake response for {system_prompt[:12]}",
            input_tokens=10,
            output_tokens=5,
        )


def test_supervisor_routes_through_required_agents() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    supervisor = SupervisorAgent()

    state = supervisor.run(state)
    assert state.route_history[-1] == "researcher"

    state.research_notes = "notes"
    state = supervisor.run(state)
    assert state.route_history[-1] == "analyst"

    state.analysis_notes = "analysis"
    state = supervisor.run(state)
    assert state.route_history[-1] == "writer"

    state.final_answer = "answer [1]"
    state = supervisor.run(state)
    assert state.route_history[-1] == "critic"

    state.critic_notes = "critic notes"
    state = supervisor.run(state)
    assert state.route_history[-1] == "done"


def test_worker_agents_populate_shared_state() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    fake_llm = FakeLLMClient()

    state = ResearcherAgent(llm_client=fake_llm).run(state)
    state = AnalystAgent(llm_client=fake_llm).run(state)
    state = WriterAgent(llm_client=fake_llm).run(state)
    state = CriticAgent(llm_client=fake_llm).run(state)

    assert state.sources
    assert state.research_notes
    assert state.analysis_notes
    assert state.final_answer
    assert state.critic_notes
