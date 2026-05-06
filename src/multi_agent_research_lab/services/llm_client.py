"""LLM client abstraction.

Production note: agents should depend on this interface instead of importing an SDK directly.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from tenacity import RetryError, Retrying, stop_after_attempt, wait_exponential

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.errors import AgentExecutionError


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class LLMClient:
    """Provider-agnostic LLM client backed by OpenAI Chat Completions."""

    # Approximate public pricing for gpt-4o-mini. Keep this as an estimate only;
    # invoices/provider dashboards remain the source of truth for final cost.
    _KNOWN_PRICES_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
        "gpt-4o-mini": (0.15, 0.60),
    }

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> None:
        self.settings = settings or get_settings()
        self.temperature = temperature
        self.max_retries = max_retries
        self._client: Any | None = None

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return a model completion with retry, timeout, usage, and cost metadata."""

        if not self.settings.openai_api_key:
            raise AgentExecutionError(
                "OPENAI_API_KEY is required for real LLM calls. "
                "Add it to .env before running CLI commands."
            )

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                reraise=True,
            ):
                with attempt:
                    response = self._openai_client().chat.completions.create(
                        model=self.settings.openai_model,
                        temperature=self.temperature,
                        timeout=self.settings.timeout_seconds,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    )
                    message = response.choices[0].message.content
                    if not message:
                        raise AgentExecutionError("OpenAI returned an empty completion.")
                    usage = getattr(response, "usage", None)
                    input_tokens = getattr(usage, "prompt_tokens", None)
                    output_tokens = getattr(usage, "completion_tokens", None)
                    return LLMResponse(
                        content=message.strip(),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=self._estimate_cost(input_tokens, output_tokens),
                    )
        except RetryError as exc:
            raise AgentExecutionError(f"OpenAI completion failed after retries: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, AgentExecutionError):
                raise
            raise AgentExecutionError(f"OpenAI completion failed: {exc}") from exc

        raise AgentExecutionError("OpenAI completion failed without returning a response.")

    def _openai_client(self) -> Any:
        if self._client is None:
            try:
                openai_module = import_module("openai")
            except ImportError as exc:
                raise AgentExecutionError(
                    "The openai package is not installed. Run `pip install -e \".[dev,llm]\"`."
                ) from exc
            openai_factory = openai_module.OpenAI
            self._client = openai_factory(api_key=self.settings.openai_api_key)
        return self._client

    def _estimate_cost(
        self,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> float | None:
        if input_tokens is None or output_tokens is None:
            return None
        model_key = self.settings.openai_model.lower()
        prices = self._KNOWN_PRICES_PER_1M_TOKENS.get(model_key)
        if prices is None:
            return None
        input_price, output_price = prices
        return (input_tokens / 1_000_000 * input_price) + (
            output_tokens / 1_000_000 * output_price
        )
