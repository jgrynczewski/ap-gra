"""The only place that talks to the AI (Claude API).

Every call is logged before it is sent (the full request) and after the
answer comes (the full answer, tokens, request id) - or the error. Nothing
else in the code may call the API, so nothing reaches the AI unlogged.

The answer is JSON in a fixed shape (output_config.format with a JSON
schema), so the code gets data, not free text. The key comes from
ANTHROPIC_API_KEY (the .env file of the ap-gra-kreator service).
"""

from __future__ import annotations

import json
import os

from engine.log import Log

MODEL = os.environ.get("AP_GRA_MODEL", "claude-opus-5-5")
# Questions are short - medium is enough and keeps the wait short
EFFORT = os.environ.get("AP_GRA_EFFORT", "medium")
# Writing the game (outline, scenario, story check) - nobody waits for it
# live, the quality matters more
GAME_EFFORT = os.environ.get("AP_GRA_EFFORT_GRA", "high")
MAX_TOKENS = 16000
GAME_MAX_TOKENS = 64000  # a whole scenario with thinking
# On a refusal by the safety classifiers the API itself retries on a model
# chosen by the refusal category (server-side fallback)
BETAS = ["server-side-fallback-2026-07-01"]


class AIError(Exception):
    """The AI did not give a usable answer (no key, network, refusal,
    answer cut off, not JSON). The message is for the log, not the user."""


def default_client():
    import anthropic

    # Retries of 429/5xx/network errors are done by the SDK (3 tries)
    return anthropic.Anthropic(max_retries=3, timeout=120.0)


def configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


class AI:
    def __init__(self, client=None, model: str = MODEL, effort: str = EFFORT):
        self._client = client
        self.model = model
        self.effort = effort

    @property
    def client(self):
        if self._client is None:
            self._client = default_client()
        return self._client

    def ask(self, log: Log, purpose: str, system: str, messages: list[dict], schema: dict,
            effort: str | None = None, max_tokens: int = MAX_TOKENS) -> dict:
        """Send the conversation, return the answer as a dict matching schema.

        Streamed (the SDK collects the whole message): a long answer, like a
        scenario, would not fit the time limit of a single request."""
        request = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {"effort": effort or self.effort,
                              "format": {"type": "json_schema", "schema": schema}},
            "betas": BETAS,
            "fallbacks": "default",
        }
        log.write("ai_zapytanie", cel=purpose, zapytanie=request)
        try:
            with self.client.beta.messages.stream(**request) as stream:
                response = stream.get_final_message()
        except Exception as error:  # noqa: BLE001 - every failure is logged, then reported
            log.write("ai_blad", cel=purpose, blad=f"{type(error).__name__}: {error}")
            raise AIError(f"{type(error).__name__}: {error}") from error

        # After a fallback mid-answer the text before the switch is a partial
        # answer of the first model - only the text after the last switch counts
        text = ""
        for block in response.content:
            if block.type == "fallback":
                text = ""
            elif block.type == "text":
                text += block.text
        usage = response.usage
        log.write("ai_odpowiedz", cel=purpose, odpowiedz=text,
                  model=response.model, powod_konca=response.stop_reason,
                  id_zapytania=getattr(response, "_request_id", None),
                  tokeny={"wejscie": usage.input_tokens, "wyjscie": usage.output_tokens,
                          "z_pamieci": getattr(usage, "cache_read_input_tokens", None)})
        if response.stop_reason == "refusal":
            raise AIError("AI odmówiło odpowiedzi")
        if response.stop_reason == "max_tokens":
            raise AIError("odpowiedź AI ucięta (max_tokens)")
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise AIError(f"odpowiedź AI to nie JSON: {error}") from error
