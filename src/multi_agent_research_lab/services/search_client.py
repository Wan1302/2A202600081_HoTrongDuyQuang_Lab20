"""Search client abstraction for ResearcherAgent."""

from multi_agent_research_lab.core.schemas import SourceDocument


class SearchClient:
    """Provider-agnostic search client with a deterministic local corpus fallback."""

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

        The lab keeps this deterministic so tests and demos can run without a paid search API.
        Replace this class with Tavily/Bing/SerpAPI later if live web search is required.
        """

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
