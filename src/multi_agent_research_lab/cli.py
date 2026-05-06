"""Command-line entrypoint for the lab."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import langsmith_trace_context, trace_span
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.storage import LocalArtifactStore

app = typer.Typer(help="Multi-Agent Research Lab CLI")
console = Console()

DEFAULT_BENCHMARK_QUERIES = [
    "Research GraphRAG state-of-the-art and write a 500-word summary",
    "Compare single-agent and multi-agent workflows for customer support",
    "Summarize production guardrails for LLM agents",
]


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


def run_single_agent(query: str) -> ResearchState:
    """Run the real LLM single-agent baseline."""

    request = ResearchQuery(query=query)
    state = ResearchState(request=request)
    settings = get_settings()
    with langsmith_trace_context(
        settings=settings,
        metadata={"workflow": "single_agent_baseline", "query": query},
    ), trace_span(
        "single_agent_baseline",
        {"model": settings.openai_model},
        run_type="chain",
        inputs={"query": query, "audience": request.audience},
        settings=settings,
    ) as span:
        response = LLMClient(settings=settings, temperature=0.3).complete(
            system_prompt=(
                "<persona>\n"
                "You are a single-agent research assistant responsible for the full task: "
                "reasoning, synthesis, and final writing.\n"
                "</persona>\n\n"
                "<rules>\n"
                "- Answer the user query directly.\n"
                "- State assumptions when the query is ambiguous.\n"
                "- Include limitations and source suggestions when relevant.\n"
                "</rules>\n\n"
                "<tools_instructions>\n"
                "You do not have live search tools in this baseline run. "
                "If evidence is needed, name the kinds of sources the user should verify.\n"
                "</tools_instructions>\n\n"
                "<response_format>\n"
                "Return a clear answer with short sections, practical takeaways, "
                "and limitations.\n"
                "</response_format>\n\n"
                "<constraints>\n"
                "Do not invent citations or claim live verification.\n"
                "</constraints>"
            ),
            user_prompt=f"Query: {query}\nAudience: {request.audience}",
        )
        span["outputs"] = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_usd": response.cost_usd,
        }
    state.final_answer = response.content
    total_tokens = None
    if response.input_tokens is not None and response.output_tokens is not None:
        total_tokens = response.input_tokens + response.output_tokens
    state.agent_results.append(
        AgentResult(
            agent=AgentName.WRITER,
            content=response.content,
            metadata={
                "mode": "single_agent_baseline",
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": response.cost_usd,
            },
        )
    )
    state.add_trace_event(
        "baseline.completed",
        {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_usd": response.cost_usd,
        },
    )
    return state


def run_multi_agent(query: str) -> ResearchState:
    """Run the Supervisor -> Researcher -> Analyst -> Writer workflow."""

    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow()
    return workflow.run(state)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the real single-agent baseline."""

    _init()
    result = run_single_agent(query)
    console.print(Panel.fit(result.final_answer or "", title="Single-Agent Baseline"))


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the multi-agent workflow."""

    _init()
    result = run_multi_agent(query)
    console.print(result.model_dump_json(indent=2))


@app.command()
def benchmark(
    queries: Annotated[
        list[str] | None,
        typer.Option("--query", "-q", help="Benchmark query. Repeat to add more."),
    ] = None,
) -> None:
    """Benchmark single-agent and multi-agent runs and write a markdown report."""

    _init()
    benchmark_queries = queries or DEFAULT_BENCHMARK_QUERIES
    metrics = []
    for index, query in enumerate(benchmark_queries, start=1):
        console.print(f"Running benchmark query {index}: {query}")
        _, baseline_metrics = run_benchmark(f"baseline-q{index}", query, run_single_agent)
        _, multi_metrics = run_benchmark(f"multi-agent-q{index}", query, run_multi_agent)
        metrics.extend([baseline_metrics, multi_metrics])

    report = render_markdown_report(metrics)
    path = LocalArtifactStore().write_text("benchmark_report.md", report)
    console.print(Panel.fit(report, title=f"Wrote {path}"))


if __name__ == "__main__":
    app()
