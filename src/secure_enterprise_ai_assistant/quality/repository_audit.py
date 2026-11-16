"""Deterministic repository hygiene and release-contract audit."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

from secure_enterprise_ai_assistant import __version__
from secure_enterprise_ai_assistant.evaluation.evidence import validate_evidence

REQUIRED_FILES = {
    ".dockerignore",
    ".env.example",
    ".github/workflows/ci.yml",
    ".gitignore",
    "Dockerfile",
    "LICENSE",
    "Makefile",
    "README.md",
    "RESPONSIBLE_USE.md",
    "SECURITY.md",
    "pyproject.toml",
    "reports/evaluation/latest.json",
    "requirements/lock-py313.txt",
}
FORBIDDEN_TRACKED_PARTS = {
    ".DS_Store",
    ".env",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "runtime",
    "tmp",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # A filled-in signing key in an env-style file (JWT_SECRET=<value>).
    re.compile(r"^[ \t]*JWT_SECRET[ \t]*=[ \t]*\S{16,}", re.MULTILINE),
)
OVERCLAIM_PATTERNS = (
    re.compile(r"\b(?:is|are|remains?)\s+enterprise-ready\b", re.I),
    re.compile(r"\b(?:is|are|remains?)\s+bank-grade\b", re.I),
    re.compile(r"\bproduction[- ]proven\b", re.I),
    re.compile(r"\bzero hallucinations?\b", re.I),
    re.compile(r"\b(?:is|are|fully)\s+regulatory compliant\b", re.I),
)


class RepositoryAuditError(RuntimeError):
    """Raised when one or more repository release contracts fail."""


def _tracked_files(repository_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    return [repository_root / item.decode() for item in result.stdout.split(b"\0") if item]


def audit_repository(repository_root: Path) -> list[str]:
    """Audit the explicit repository root and return human-readable successful checks."""
    root = repository_root.resolve()
    failures: list[str] = []
    files = _tracked_files(root)
    relative_files = {path.relative_to(root).as_posix() for path in files}

    missing = sorted(REQUIRED_FILES - relative_files)
    if missing:
        failures.append(f"Pflichtdateien fehlen: {missing}")

    for path in files:
        relative = path.relative_to(root)
        if any(part in FORBIDDEN_TRACKED_PARTS for part in relative.parts):
            failures.append(f"verbotenes Artefakt im Repository: {relative}")
        if path.is_symlink() and not path.resolve().is_relative_to(root):
            failures.append(f"symbolischer Link zeigt aus dem Repository: {relative}")
        if path.is_file() and path.stat().st_size > 10 * 1024 * 1024:
            failures.append(f"Datei größer als 10 MiB: {relative}")

    for path in files:
        if not path.is_file() or path.suffix.lower() in {".docx", ".pdf", ".png", ".pptx"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"mögliches Geheimnis in {path.relative_to(root)}")
        if path.name.lower() not in {"license", "security.md", "responsible_use.md"}:
            for pattern in OVERCLAIM_PATTERNS:
                if pattern.search(text):
                    failures.append(
                        f"unbelegte Behauptung '{pattern.pattern}' in {path.relative_to(root)}"
                    )

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject["project"]["version"] != __version__:
        failures.append("Versionen in pyproject und Paket weichen ab")

    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in files
        if path.is_file() and path.suffix == ".py" and "tests" not in path.parts
    )
    forbidden_import_overrides = ("sys.path" + ".insert", "PYTHON" + "PATH")
    if any(marker in source_text for marker in forbidden_import_overrides):
        failures.append("Quellcode verbiegt den Importpfad")
    if re.search(r"Path\(__file__\).*parents\[[2-9]\]", source_text):
        failures.append("Paketcode leitet das Repository-Verzeichnis aus __file__ ab")

    try:
        validate_evidence(root / "reports" / "evaluation" / "latest.json")
    except Exception as exc:
        failures.append(f"Evaluationsbericht ungültig: {exc}")

    if failures:
        raise RepositoryAuditError("\n".join(f"- {failure}" for failure in failures))
    return [
        f"{len(files)} versionierte Dateien geprüft",
        "alle Pflichtdateien vorhanden",
        "keine Caches, Umgebungen, Laufzeitdaten oder übergroßen Dateien",
        "keine bekannten Geheimnis-Muster und keine unbelegten Behauptungen",
        "Paketversion und Evaluationsbericht passen zusammen",
    ]
