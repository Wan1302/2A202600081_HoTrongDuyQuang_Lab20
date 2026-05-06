"""Tracing hooks for local JSON traces and optional LangSmith runs."""

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from time import perf_counter
from typing import Any

from multi_agent_research_lab.core.config import Settings, get_settings


@contextmanager
def langsmith_trace_context(
    *,
    settings: Settings | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Enable LangSmith tracing for a block when configured.

    Local JSON tracing still works even when LangSmith is disabled or unavailable.
    """

    settings = settings or get_settings()
    if not _langsmith_enabled(settings):
        with nullcontext():
            yield
        return

    try:
        from langsmith import Client
        from langsmith.run_helpers import tracing_context
    except ImportError:
        with nullcontext():
            yield
        return

    client = Client(api_key=settings.langsmith_api_key, api_url=settings.langsmith_endpoint)
    try:
        with tracing_context(
            project_name=settings.langsmith_project,
            tags=["lab20", "multi-agent-research"],
            metadata=metadata or {},
            enabled=True,
            client=client,
        ):
            yield
    finally:
        client.flush()


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    *,
    run_type: str = "chain",
    inputs: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> Iterator[dict[str, Any]]:
    """Create a local span and, when configured, a matching LangSmith run."""

    settings = settings or get_settings()
    started = perf_counter()
    span: dict[str, Any] = {
        "name": name,
        "attributes": attributes or {},
        "duration_seconds": None,
        "outputs": None,
    }

    if not _langsmith_enabled(settings):
        try:
            yield span
        finally:
            span["duration_seconds"] = perf_counter() - started
        return

    try:
        from langsmith.run_helpers import trace
    except ImportError:
        try:
            yield span
        finally:
            span["duration_seconds"] = perf_counter() - started
        return

    with trace(
        name,
        run_type=run_type,  # type: ignore[arg-type]
        inputs=inputs or {},
        project_name=settings.langsmith_project,
        metadata=attributes or {},
    ) as run:
        span["langsmith_run_id"] = str(run.id)
        try:
            yield span
        finally:
            span["duration_seconds"] = perf_counter() - started
            run.end(outputs=_langsmith_outputs(span))


def _langsmith_enabled(settings: Settings) -> bool:
    return bool(settings.langsmith_tracing and settings.langsmith_api_key)


def _langsmith_outputs(span: dict[str, Any]) -> dict[str, Any]:
    outputs = span.get("outputs")
    if isinstance(outputs, dict):
        return {
            **outputs,
            "duration_seconds": span.get("duration_seconds"),
        }
    return {"duration_seconds": span.get("duration_seconds")}
