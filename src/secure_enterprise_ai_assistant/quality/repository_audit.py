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
        failures.append(f"missing required files: {missing}")

    for path in files:
        relative = path.relative_to(root)
        if any(part in FORBIDDEN_TRACKED_PARTS for part in relative.parts):
            failures.append(f"forbidden tracked or versionable artifact: {relative}")
        if path.is_symlink() and not path.resolve().is_relative_to(root):
            failures.append(f"symlink escapes repository: {relative}")
        if path.is_file() and path.stat().st_size > 10 * 1024 * 1024:
            failures.append(f"unexpected file larger than 10 MiB: {relative}")

    for path in files:
        if not path.is_file() or path.suffix.lower() in {".docx", ".pdf", ".png", ".pptx"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"possible secret in {path.relative_to(root)}")
        if path.name.lower() not in {"license", "security.md", "responsible_use.md"}:
            for pattern in OVERCLAIM_PATTERNS:
                if pattern.search(text):
                    failures.append(
                        f"unsupported claim '{pattern.pattern}' in {path.relative_to(root)}"
                    )

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject["project"]["version"] != __version__:
        failures.append("pyproject and package versions differ")

    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in files
        if path.is_file() and path.suffix == ".py" and "tests" not in path.parts
    )
    forbidden_import_overrides = ("sys.path" + ".insert", "PYTHON" + "PATH")
    if any(marker in source_text for marker in forbidden_import_overrides):
        failures.append("source relies on an import-path override")
    if re.search(r"Path\(__file__\).*parents\[[2-9]\]", source_text):
        failures.append("package source derives a repository root from __file__")

    try:
        validate_evidence(root / "reports" / "evaluation" / "latest.json")
    except Exception as exc:
        failures.append(f"evaluation evidence invalid: {exc}")

    if failures:
        raise RepositoryAuditError("\n".join(f"- {failure}" for failure in failures))
    return [
        f"{len(files)} tracked/versionable files inspected",
        "required release files present",
        "no tracked cache, environment, runtime, or oversized artifacts",
        "no known secret signatures or prohibited overclaims",
        "package version and evaluation evidence are consistent",
    ]
