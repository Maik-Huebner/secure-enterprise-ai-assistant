"""Secure Markdown/PDF ingestion with provenance-preserving section chunking."""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from secure_enterprise_ai_assistant.guardrails import scan_untrusted_content
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeChunk

METADATA_FIELDS = {
    "Document-ID": "document_id",
    "Title": "title",
    "Version": "version",
    "Effective-Date": "effective_date",
    "Owner": "owner",
}


class KnowledgeIngestor:
    """Load only approved local knowledge files below a configured root."""

    def __init__(self, knowledge_root: Path, max_chunk_chars: int = 1200) -> None:
        self.knowledge_root = knowledge_root.resolve()
        self.max_chunk_chars = max_chunk_chars

    def ingest_directory(self) -> list[KnowledgeChunk]:
        """Ingest supported files in deterministic filename order."""
        chunks: list[KnowledgeChunk] = []
        for path in sorted(self.knowledge_root.iterdir()):
            if path.suffix.lower() in {".md", ".txt", ".pdf"}:
                chunks.extend(self.ingest_file(path))
        return chunks

    def ingest_file(self, path: Path) -> list[KnowledgeChunk]:
        """Validate path containment and load a supported document."""
        resolved = path.resolve()
        if not resolved.is_relative_to(self.knowledge_root):
            raise ValueError("Knowledge file must remain inside the configured root.")
        if resolved.suffix.lower() == ".pdf":
            return self._ingest_pdf(resolved)
        if resolved.suffix.lower() in {".md", ".txt"}:
            return self._ingest_text(resolved)
        raise ValueError(f"Unsupported knowledge file type: {resolved.suffix}")

    def _ingest_text(self, path: Path) -> list[KnowledgeChunk]:
        text = path.read_text(encoding="utf-8")
        metadata = self._metadata(text, path)
        sections = self._sections(text)
        return self._build_chunks(metadata, sections)

    def _ingest_pdf(self, path: Path) -> list[KnowledgeChunk]:
        with pdfplumber.open(path) as pdf:
            pages = [
                (number, page.extract_text() or "")
                for number, page in enumerate(pdf.pages, 1)
            ]
        full_text = "\n".join(text for _, text in pages)
        metadata = self._metadata(full_text, path)
        sections = [(f"Page {page}", text, page) for page, text in pages if text.strip()]
        return self._build_chunks(metadata, sections)

    @staticmethod
    def _metadata(text: str, path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for label, key in METADATA_FIELDS.items():
            match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, flags=re.MULTILINE)
            if match:
                values[key] = match.group(1).strip()
        values.setdefault("document_id", path.stem.upper())
        values.setdefault("title", path.stem.replace("-", " ").title())
        values.setdefault("version", "unknown")
        values.setdefault("effective_date", "unknown")
        values.setdefault("owner", "unknown")
        return values

    @staticmethod
    def _sections(text: str) -> list[tuple[str, str, int | None]]:
        sections: list[tuple[str, str, int | None]] = []
        current_title = "Document metadata"
        current_lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("## "):
                if content := "\n".join(current_lines).strip():
                    sections.append((current_title, content, None))
                current_title = line[3:].strip()
                current_lines = []
            elif not line.startswith("# "):
                current_lines.append(line)
        if content := "\n".join(current_lines).strip():
            sections.append((current_title, content, None))
        return sections

    def _build_chunks(
        self,
        metadata: dict[str, str],
        sections: list[tuple[str, str, int | None]],
    ) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        sequence = 0
        for section, content, page in sections:
            paragraphs = [item.strip() for item in content.split("\n\n") if item.strip()]
            buffer = ""
            for paragraph in paragraphs:
                candidate = f"{buffer}\n\n{paragraph}".strip()
                if buffer and len(candidate) > self.max_chunk_chars:
                    sequence += 1
                    chunks.append(self._chunk(metadata, section, page, sequence, buffer))
                    buffer = paragraph
                else:
                    buffer = candidate
            if buffer:
                sequence += 1
                chunks.append(self._chunk(metadata, section, page, sequence, buffer))
        return chunks

    @staticmethod
    def _chunk(
        metadata: dict[str, str],
        section: str,
        page: int | None,
        sequence: int,
        content: str,
    ) -> KnowledgeChunk:
        return KnowledgeChunk(
            chunk_id=f"{metadata['document_id']}::chunk-{sequence:03d}",
            document_id=metadata["document_id"],
            title=metadata["title"],
            version=metadata["version"],
            effective_date=metadata["effective_date"],
            owner=metadata["owner"],
            section=section,
            page=page,
            content=content,
            security_flags=scan_untrusted_content(content),
        )
