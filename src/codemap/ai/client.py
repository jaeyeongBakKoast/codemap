from __future__ import annotations

import json
import logging
import re
import socket
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

_TIMEOUT = 60
_RETRYABLE = (socket.timeout, TimeoutError)


class AiClient:
    def __init__(self, base_url: str, model: str, language: str = "ko"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.language = language
        self._disabled = False

    @property
    def available(self) -> bool:
        return not self._disabled

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        if self._disabled:
            return ""

        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }).encode()

        url = f"{self.base_url}/v1/chat/completions"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
        )

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
            except ConnectionRefusedError:
                logger.warning("AI server connection refused — disabling AI enrichment")
                self._disabled = True
                return ""
            except urllib.error.HTTPError as e:
                if attempt == 0:
                    logger.info("AI request failed (%s), retrying...", e)
                    continue
                logger.warning("AI server error — disabling AI enrichment: %s", e)
                self._disabled = True
                return ""
            except urllib.error.URLError as e:
                if isinstance(e.reason, _RETRYABLE) and attempt == 0:
                    logger.info("AI request timed out, retrying...")
                    continue
                logger.warning("AI server unreachable — disabling AI enrichment: %s", e)
                self._disabled = True
                return ""
            except OSError as e:
                if attempt == 0:
                    logger.info("AI request failed (%s), retrying...", e)
                    continue
                logger.warning("AI server error — disabling AI enrichment: %s", e)
                self._disabled = True
                return ""
            except (KeyError, json.JSONDecodeError) as e:
                logger.warning("AI response parse error: %s", e)
                return ""

        return ""

    def chat_json(self, system: str, user: str, temperature: float = 0.3) -> dict | None:
        text = self.chat(system, user, temperature)
        if not text:
            return None

        stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
        stripped = re.sub(r"\n?```\s*$", "", stripped)

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            logger.warning("AI returned invalid JSON: %s", text[:200])
            return None
