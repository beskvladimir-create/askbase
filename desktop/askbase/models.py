"""Finding and talking to a model that is already on this computer.

Askbase does not download anything and does not reach a hosted model. It talks
to a local server over the OpenAI-compatible endpoint Ollama exposes on the
loopback address, which is why the application works with the network off.
"""
from __future__ import annotations

import contextlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

HOST = "http://127.0.0.1:11434"
# Own opener, with proxies switched off. urllib otherwise reads http_proxy from
# the environment and sends even a request to 127.0.0.1 through the proxy: the
# offline guard refuses that, and the user is told the local model is not
# running when it is running and listening. Having our own opener also keeps the
# choice out of urllib's global one, which is built on the first call and then
# keeps whatever the environment said at that moment for the rest of the run.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# Models known to be trained for SQL are offered first: a general chat model
# will answer, but it writes prose around the query and takes several times
# longer, which on a laptop is the difference between four seconds and a minute.
PREFERRED = ("xiyansql", "arctic-text2sql", "sqlcoder", "omnisql", "qwen2.5-coder", "coder")


def installed_models(timeout: float = 2.0, *, host: str = HOST) -> list[str]:
    """Local model names, the SQL-capable ones first. Empty if Ollama is absent."""
    try:
        with _OPENER.open(f"{host}/api/tags", timeout=timeout) as r:
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


class Cancelled(Exception):
    """The question was stopped. Not a failure, and nothing to report."""


class ModelClient:
    """Minimal client. No SDK, so the packaged application stays small."""

    def __init__(self, model: str, *, host: str = HOST, timeout: float = 180.0,
                 max_tokens: int = 1024):
        self.model = model
        self.host = host
        self.timeout = timeout
        self.max_tokens = max_tokens
        self._live = None           # the reply being read, so that it can be dropped
        self._cancelled = False

    def reset(self) -> None:
        """A stopped question must not stop the next one."""
        self._cancelled = False

    def cancel(self) -> None:
        """Give up on the answer. Called from the interface thread while one is being read.

        Abandoning the result in the window is not enough: one model answers
        one question at a time, so until this connection is dropped the next
        question waits behind a question nobody wants any more.
        """
        self._cancelled = True
        live = self._live
        if live is not None:
            # It may already have finished, in which case the flag is enough.
            with contextlib.suppress(Exception):
                live.close()

    def complete(self, prompt: str, temperature: float = 0.0) -> Completion:
        if self._cancelled:
            raise Cancelled
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
            with _OPENER.open(req, timeout=self.timeout) as r:
                self._live = r
                data = json.load(r)
        except TimeoutError as e:
            # A read timeout is not a URLError, so it used to travel up as an
            # unexpected error with a traceback. On a laptop without a GPU a
            # large model running out of time is routine, not a defect.
            raise RuntimeError(
                f"Модель не ответила за {self.timeout:.0f} с. "
                "Попробуйте модель меньше или вопрос попроще."
            ) from e
        except (urllib.error.URLError, OSError) as e:
            # A connection the interface dropped looks exactly like a model
            # that went away, so what the user did decides which one it was.
            if self._cancelled:
                raise Cancelled from None
            raise RuntimeError(
                "Локальная модель не отвечает. Проверьте, что Ollama запущена."
            ) from e
        except ValueError as e:
            if self._cancelled:
                raise Cancelled from None
            # Not JSON: something other than the model answered on that port.
            raise RuntimeError(
                "Ответ локальной модели не разобрался. Проверьте, что на 11434 отвечает Ollama."
            ) from e
        finally:
            self._live = None
        return Completion(
            text=(data.get("message") or {}).get("content", ""),
            seconds=time.perf_counter() - t0,
        )
