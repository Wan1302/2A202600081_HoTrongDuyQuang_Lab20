"""Search client abstraction for ResearcherAgent."""

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import SourceDocument


class SearchClient:
    """Provider-agnostic search client with Tavily live search and local fallback."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        tavily_api_key: str | None = None,
        tavily_endpoint: str = "https://api.tavily.com/search",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.settings = settings or get_settings()
        self.tavily_api_key = (
            tavily_api_key if tavily_api_key is not None else self.settings.tavily_api_key
        )
        self.tavily_endpoint = tavily_endpoint
        self.timeout_seconds = timeout_seconds

    _LOCAL_CORPUS: tuple[SourceDocument, ...] = (
        SourceDocument(
            title="Anthropic: Building Effective Agents",
            url="https://www.anthropic.com/engineering/building-effective-agents",
            snippet=(
                "Practical guidance for agentic systems: start with the simplest workflow, "
                "compose agents when specialization improves reliability, and add guardrails."
            ),
        ),
        SourceDocument(
            title="OpenAI Agents SDK: Orchestration and Handoffs",
            url="https://developers.openai.com/api/docs/guides/agents/orchestration",
            snippet=(
                "Describes supervisor-style orchestration, handoffs between agents, tool use, "
                "and tracing for agent applications."
            ),
        ),
        SourceDocument(
            title="LangGraph Concepts",
            url="https://langchain-ai.github.io/langgraph/concepts/",
            snippet=(
                "Explains stateful graph workflows for LLM applications, including nodes, edges, "
                "conditional routing, retries, and persistence."
            ),
        ),
        SourceDocument(
            title="LangSmith Tracing Documentation",
            url="https://docs.smith.langchain.com/",
            snippet=(
                "Observability platform for tracing agent runs, measuring latency, inspecting "
                "intermediate steps, and debugging failures."
            ),
        ),
        SourceDocument(
            title="Microsoft Research: From Local to Global GraphRAG",
            url=(
                "https://www.microsoft.com/en-us/research/publication/"
                "from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/"
            ),
            snippet=(
                "GraphRAG builds graph-based indexes over document collections to improve "
                "query-focused summarization across local and global contexts."
            ),
        ),
        SourceDocument(
            title="Langfuse LLM Observability",
            url="https://langfuse.com/docs",
            snippet=(
                "Open-source LLM observability with traces, spans, prompt tracking, scores, "
                "and cost monitoring for production LLM applications."
            ),
        ),
    )

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query.

        If `TAVILY_API_KEY` is configured, this performs live Tavily search. If Tavily is
        unavailable or returns no usable result, the deterministic local corpus keeps tests
        and demos reproducible.
        """

        if self.tavily_api_key:
            tavily_results = self._search_tavily(query, max_results=max_results)
            if tavily_results:
                return tavily_results
        return self._search_local(query, max_results=max_results)

    def _search_local(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        query_terms = {term.strip(".,:;!?()[]{}").lower() for term in query.split()}
        scored: list[tuple[int, SourceDocument]] = []
        for document in self._LOCAL_CORPUS:
            haystack = f"{document.title} {document.snippet}".lower()
            score = sum(1 for term in query_terms if term and term in haystack)
            scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [document for score, document in scored if score > 0][:max_results]
        if selected:
            return selected
        return list(self._LOCAL_CORPUS[:max_results])

    def _search_tavily(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        try:
            payload = self._request_tavily(query, max_results=max_results)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return []
        return _parse_tavily_results(payload)

    def _request_tavily(self, query: str, max_results: int = 5) -> dict[str, Any]:
        body = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }
        request = Request(
            self.tavily_endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.tavily_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
        payload = json.loads(response_body)
        if not isinstance(payload, dict):
            return {}
        return payload


def _parse_tavily_results(payload: dict[str, Any]) -> list[SourceDocument]:
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    sources: list[SourceDocument] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = _optional_string(item.get("url"))
        title = _optional_string(item.get("title")) or url or "Untitled Tavily result"
        snippet = (
            _optional_string(item.get("content"))
            or _optional_string(item.get("snippet"))
            or _optional_string(item.get("raw_content"))
        )
        if not snippet:
            continue

        metadata: dict[str, Any] = {"provider": "tavily"}
        score = item.get("score")
        if isinstance(score, int | float):
            metadata["score"] = float(score)
        published_date = _optional_string(item.get("published_date"))
        if published_date:
            metadata["published_date"] = published_date

        sources.append(
            SourceDocument(
                title=title,
                url=url,
                snippet=snippet,
                metadata=metadata,
            )
        )
    return sources


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
