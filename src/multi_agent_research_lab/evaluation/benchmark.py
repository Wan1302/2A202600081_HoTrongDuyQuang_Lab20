"""Benchmark utilities for single-agent vs multi-agent."""

from collections.abc import Callable
from time import perf_counter

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState

Runner = Callable[[str], ResearchState]


def run_benchmark(
    run_name: str,
    query: str,
    runner: Runner,
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency, usage, citation coverage, and failure status."""

    started = perf_counter()
    state = runner(query)
    latency = perf_counter() - started
    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency,
        estimated_cost_usd=_sum_float_metadata(state, "cost_usd"),
        citation_coverage=_citation_coverage(state),
        failure_rate=1.0 if state.errors else 0.0,
        total_tokens=_sum_int_metadata(state, "total_tokens"),
        notes=_benchmark_notes(state),
    )
    return state, metrics


def _sum_float_metadata(state: ResearchState, key: str) -> float | None:
    total = 0.0
    found = False
    for result in state.agent_results:
        value = result.metadata.get(key)
        if isinstance(value, int | float):
            total += float(value)
            found = True
    return total if found else None


def _sum_int_metadata(state: ResearchState, key: str) -> int | None:
    total = 0
    found = False
    for result in state.agent_results:
        value = result.metadata.get(key)
        if isinstance(value, int):
            total += value
            found = True
    return total if found else None


def _citation_coverage(state: ResearchState) -> float | None:
    if not state.sources:
        return None
    final_answer = state.final_answer or ""
    cited = sum(
        1
        for index in range(1, len(state.sources) + 1)
        if f"[{index}]" in final_answer
    )
    return cited / len(state.sources)


def _benchmark_notes(state: ResearchState) -> str:
    parts: list[str] = []
    if state.errors:
        parts.append(f"errors={len(state.errors)}")
    if state.route_history:
        parts.append("route=" + " > ".join(state.route_history))
    if not parts:
        parts.append("completed")
    return "; ".join(parts)
