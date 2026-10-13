"""Chat-completions client."""

from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

RETRYABLE = {408, 429, 500, 502, 503, 504}


def message_text(result: dict) -> str:
    try:
        choice = result["choices"][0]
        text = choice["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Model endpoint returned an invalid chat-completions response") from None
    if choice.get("finish_reason") not in (None, "stop"):
        raise ValueError("Model response did not finish normally")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Model returned no text")
    return text


class LLMClient:
    """Chat-completions client for any OpenAI-compatible endpoint."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "")).rstrip("/")
        if not api_key or not model:
            raise ValueError("Set LLM_API_KEY and a model name")
        if urlsplit(self.base_url).scheme not in {"http", "https"}:
            raise ValueError("LLM_BASE_URL must be an http(s) URL")

    def generate(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
        }
        request = Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
        )
        for delay in (1, 2):
            text = self._send(request, final=False)
            if text is not None:
                return text
            time.sleep(delay)
        return self._send(request, final=True)

    def _send(self, request: Request, *, final: bool) -> str | None:
        """One request; None asks the caller to retry a transient failure."""
        try:
            with urlopen(request, timeout=180) as response:
                result = json.load(response)
        except HTTPError as exc:
            if exc.code in RETRYABLE and not final:
                return None
            raise RuntimeError(f"Model request failed with HTTP {exc.code}") from None
        except (URLError, TimeoutError):
            if not final:
                return None
            raise RuntimeError("Model request failed after three attempts") from None
        except json.JSONDecodeError:
            raise ValueError("Model endpoint returned an invalid chat-completions response") from None
        return message_text(result)
