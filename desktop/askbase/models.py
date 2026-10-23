"""Finding and talking to a model that is already on this computer.

Askbase does not download anything and does not reach a hosted model. It talks
to a local server over the OpenAI-compatible endpoint Ollama exposes on the
loopback address, which is why the application works with the network off.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

HOST = "http://127.0.0.1:11434"
# Models known to be trained for SQL are offered first: a general chat model
# will answer, but it writes prose around the query and takes several times
# longer, which on a laptop is the difference between four seconds and a minute.
PREFERRED = ("xiyansql", "arctic-text2sql", "sqlcoder", "omnisql", "qwen2.5-coder", "coder")


def installed_models(timeout: float = 2.0) -> list[str]:
    """Local model names, the SQL-capable ones first. Empty if Ollama is absent."""
    try:
        with urllib.request.urlopen(f"{HOST}/api/tags", timeout=timeout) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []
    names = [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    def rank(name: str) -> int:
        low = name.lower()
        for i, key in enumerate(PREFERRED):
            if key in low:
                return i
        return len(PREFERRED)

    return sorted(names, key=lambda n: (rank(n), n))


@dataclass
class Completion:
    text: str
    seconds: float


class ModelClient:
    """Minimal client. No SDK, so the packaged application stays small."""

    def __init__(self, model: str, *, host: str = HOST, timeout: float = 180.0,
                 max_tokens: int = 1024):
        self.model = model
        self.host = host
        self.timeout = timeout
        self.max_tokens = max_tokens

    def complete(self, prompt: str, temperature: float = 0.0) -> Completion:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": self.max_tokens},
        }).encode()
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.load(r)
        except urllib.error.URLError as e:
            raise RuntimeError(
                "Локальная модель не отвечает. Проверьте, что Ollama запущена."
            ) from e
        return Completion(
            text=(data.get("message") or {}).get("content", ""),
            seconds=time.perf_counter() - t0,
        )
