"""Benchmark report rendering."""

from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def render_markdown_report(metrics: list[BenchmarkMetrics]) -> str:
    """Render benchmark metrics to markdown."""

    lines = [
        "# Benchmark Report",
        "",
        "## Summary",
        "",
        (
            "This report compares a single-agent baseline with the supervised "
            "Researcher -> Analyst -> Writer workflow."
        ),
        "",
        "## Metrics",
        "",
        (
            "| Run | Latency (s) | Cost (USD) | Tokens | Citation coverage | "
            "Failure rate | Quality | Notes |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in metrics:
        lines.append(
            "| "
            f"{item.run_name} | "
            f"{item.latency_seconds:.2f} | "
            f"{_format_float(item.estimated_cost_usd, digits=4)} | "
            f"{item.total_tokens if item.total_tokens is not None else ''} | "
            f"{_format_percent(item.citation_coverage)} | "
            f"{_format_percent(item.failure_rate)} | "
            f"{_format_float(item.quality_score, digits=1)} | "
            f"{item.notes} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Baseline measures how well one LLM call handles the whole task.",
            "- Multi-agent measures the overhead and quality gain from explicit handoffs.",
            "- Quality should be filled after peer review using the 0-10 lab rubric.",
            "",
            "## Failure Mode",
            "",
            (
                "Record any timeout, missing citation, empty answer, or agent failure "
                "observed during runs."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def _format_float(value: float | None, *, digits: int) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value * 100:.0f}%"
