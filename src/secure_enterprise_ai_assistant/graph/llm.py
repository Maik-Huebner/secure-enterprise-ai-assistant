"""Answer model: a local Ollama chat model behind a small, testable interface."""

from __future__ import annotations

from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from secure_enterprise_ai_assistant.core.settings import Settings, get_settings


class AnswerModel(Protocol):
    """Generates German text from a system and a user prompt."""

    @property
    def name(self) -> str: ...

    def generate(self, system: str, user: str) -> str: ...


class OllamaAnswerModel:
    """ChatOllama with the central generation settings (temperature, tokens, timeout)."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._model = settings.ollama_fast_model
        self._chat = ChatOllama(
            model=settings.ollama_fast_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
            num_predict=settings.llm_max_tokens,
            num_ctx=settings.llm_context_tokens,
            reasoning=settings.ollama_think,
            seed=settings.llm_seed,
            client_kwargs={"timeout": settings.ollama_request_timeout_seconds},
        )

    @property
    def name(self) -> str:
        return self._model

    def generate(self, system: str, user: str) -> str:
        message = self._chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return str(message.content).strip()
