"""Model client over an OpenAI-compatible endpoint.

Works for a local vLLM server (`vllm serve ... --port 8000`) and for any cloud
reference model exposing the OpenAI API. Tracks token usage and wall-clock so the
runner can report cost/latency alongside accuracy.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:          # the SDK is imported lazily; see __post_init__
    from openai import OpenAI


@dataclass
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


@dataclass
class ModelClient:
    model: str
    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"          # vLLM ignores it; set real key for cloud ref
    temperature: float = 0.0
    max_tokens: int = 1024
    # A request timeout is a property of the harness, not of the model, so it
    # belongs in the config and in the summary where it can be audited. 90s was
    # tuned on a terse model and silently broke a verbose one: Arctic-7B writes
    # a reasoning preamble, its median reply is 316 tokens against XiYan's 45,
    # and 91 of 500 requests timed out. Those became empty predictions, scored
    # as wrong, and each one burned up to timeout x (1 + max_retries) seconds
    # first, so the same setting also halved the throughput it was measuring.
    timeout_s: float = 600.0
    max_retries: int = 2
    _client: OpenAI = field(init=False, repr=False)

    def __post_init__(self):
        from openai import OpenAI  # lazy: harness core imports without the SDK

        # Still bounded: a wedged request must fail rather than hang the stage
        # forever, which is why this is not None. Just bounded generously enough
        # that the bound never decides the score.
        self._client = OpenAI(
            base_url=self.base_url, api_key=self.api_key,
            timeout=self.timeout_s, max_retries=self.max_retries,
        )

    def complete(self, prompt: str, temperature: float | None = None) -> Completion:
        t0 = time.perf_counter()
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=self.max_tokens,
        )
        dt = time.perf_counter() - t0
        usage = resp.usage
        return Completion(
            text=resp.choices[0].message.content or "",
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            latency_s=dt,
        )
