from typing import Any

from multi_agent_research_lab.services.search_client import SearchClient


class FakeTavilySearchClient(SearchClient):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(tavily_api_key="tvly-test")
        self.payload = payload

    def _request_tavily(self, query: str, max_results: int = 5) -> dict[str, Any]:
        return self.payload


def test_search_client_uses_tavily_when_key_is_configured() -> None:
    client = FakeTavilySearchClient(
        {
            "results": [
                {
                    "title": "Live GraphRAG source",
                    "url": "https://example.com/graphrag",
                    "content": (
                        "GraphRAG combines graph indexes with retrieval-augmented generation."
                    ),
                    "score": 0.91,
                }
            ]
        }
    )

    results = client.search("GraphRAG state of the art", max_results=3)

    assert results[0].title == "Live GraphRAG source"
    assert results[0].metadata["provider"] == "tavily"
    assert results[0].metadata["score"] == 0.91


def test_search_client_falls_back_to_local_corpus_without_tavily_key() -> None:
    client = SearchClient(tavily_api_key="")

    results = client.search("GraphRAG state of the art", max_results=3)

    assert results
    assert all(source.metadata.get("provider") != "tavily" for source in results)
