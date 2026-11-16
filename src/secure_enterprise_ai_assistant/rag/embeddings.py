"""Embedding backends: hashing for fast tests, Ollama or Sentence Transformers for real use."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import faiss
import httpx
import numpy as np

TOKEN_PATTERN = re.compile(r"(?u)\b\w\w+\b")


class EmbeddingUnavailableError(RuntimeError):
    """Raised when the configured embedding backend cannot be reached."""


class Embedder(Protocol):
    """Embedding interface used by the retriever and the semantic router."""

    @property
    def name(self) -> str:
        """Stable identifier stored in the index manifest."""

    @property
    def is_semantic(self) -> bool:
        """True for meaning-based models; False for the lexical hashing bootstrap."""

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        """Return L2-normalized float32 vectors for documents."""

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        """Return L2-normalized float32 vectors for search queries."""


def _normalized(vectors: np.ndarray) -> np.ndarray:
    array = np.ascontiguousarray(vectors, dtype="float32")
    faiss.normalize_L2(array)
    return array


class HashingEmbedder:
    """Deterministic bag-of-words hashing. Lexical only; for tests and offline baselines."""

    is_semantic = False

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    @property
    def name(self) -> str:
        return f"hashing-{self.dimensions}"

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimensions), dtype="float32")
        for row, text in enumerate(texts):
            for token in TOKEN_PATTERN.findall(text.casefold()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                vectors[row, int.from_bytes(digest, "little") % self.dimensions] += 1.0
        return _normalized(vectors)

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts)

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts)


@dataclass(frozen=True)
class PromptFormat:
    """Model-card instruction prefixes for asymmetric retrieval models."""

    query: str = "{text}"
    document: str = "{text}"


# Prefixes as documented on the respective model cards. bge-m3 needs none.
PROMPT_FORMATS: dict[str, PromptFormat] = {
    "qwen3-embedding": PromptFormat(
        query=(
            "Instruct: Given a question in German, retrieve the internal policy passage that "
            "answers it\nQuery:{text}"
        ),
    ),
    "embeddinggemma": PromptFormat(
        query="task: search result | query: {text}",
        document="title: none | text: {text}",
    ),
}


def prompt_format_for(model: str) -> PromptFormat:
    """Return the prompt format for an Ollama model tag such as ``qwen3-embedding:0.6b``."""
    family = model.split(":", 1)[0]
    return PROMPT_FORMATS.get(family, PromptFormat())


class OllamaEmbedder:
    """Embeddings from a local Ollama server via ``/api/embed``."""

    is_semantic = True

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 120.0,
        batch_size: int = 32,
        prompt_format: PromptFormat | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.batch_size = batch_size
        self.prompt_format = prompt_format or prompt_format_for(model)

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def _embed(self, texts: list[str]) -> np.ndarray:
        rows: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            try:
                response = httpx.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": batch},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise EmbeddingUnavailableError(
                    f"Das Embedding-Modell {self.model} ist über Ollama nicht erreichbar. "
                    f"Läuft Ollama, und wurde das Modell mit 'ollama pull {self.model}' geladen?"
                ) from exc
            rows.extend(response.json()["embeddings"])
        return _normalized(np.asarray(rows, dtype="float32"))

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed([self.prompt_format.document.format(text=text) for text in texts])

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed([self.prompt_format.query.format(text=text) for text in texts])


class SentenceTransformerEmbedder:
    """Embeddings from a locally available Sentence Transformer (no download at runtime)."""

    is_semantic = True

    def __init__(self, model_name_or_path: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name_or_path
        self._model = SentenceTransformer(model_name_or_path, local_files_only=True)

    @property
    def name(self) -> str:
        return f"sentence-transformers:{self._model_name}"

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        values = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(values, dtype="float32")

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts)

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts)
