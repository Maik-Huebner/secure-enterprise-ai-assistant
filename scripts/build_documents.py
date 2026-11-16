"""Build the Office and PDF documents in output/ from the Markdown sources in docs/.

Needs macOS with pandoc, Google Chrome, Keynote and Node.js (``npm ci`` in tools/dokumente):

* Projektdokumentation: docs/project-documentation.md → DOCX (pandoc) and PDF (Chrome)
* Präsentation: tools/dokumente/praesentation.cjs → PPTX (pptxgenjs) → PDF (Keynote)
* Sprechertext: docs/presentation-speaker-notes.md → PDF (Chrome)

Usage: python scripts/build_documents.py [--ohne-praesentation]
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from secure_enterprise_ai_assistant.core.cli import GermanArgumentParser

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TOOLS = ROOT / "tools" / "dokumente"
OUTPUT = ROOT / "output"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
NAME = "Secure_Enterprise_AI_Assistant_FINAL"

DOCUMENTATION_DOCX = OUTPUT / "document" / f"Projektdokumentation_{NAME}.docx"
DOCUMENTATION_PDF = OUTPUT / "pdf" / f"Projektdokumentation_{NAME}.pdf"
PRESENTATION_PPTX = OUTPUT / "presentation" / f"10_Minuten_Praesentation_{NAME}.pptx"
PRESENTATION_PDF = OUTPUT / "pdf" / f"10_Minuten_Praesentation_{NAME}.pdf"
SPEAKER_NOTES_PDF = OUTPUT / "pdf" / f"Sprechertext_10_Minuten_{NAME}.pdf"


def _run(*command: str | Path) -> None:
    subprocess.run([str(part) for part in command], check=True)


def _require(tool: str) -> None:
    if shutil.which(tool) is None:
        sys.exit(f"{tool} fehlt (siehe tools/dokumente/README.md).")


def build_docx(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(
        "pandoc", source, "--from", "markdown", "--to", "docx",
        "--reference-doc", TOOLS / "referenz.docx", "--resource-path", DOCS,
        "--metadata", "lang=de-DE", "--output", target,
    )  # fmt: skip


def build_pdf(source: Path, target: Path, title: str) -> None:
    """Markdown → HTML with print CSS → PDF via headless Chrome (A4, page numbers)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        html = Path(work) / "dokument.html"
        _run(
            "pandoc", source, "--from", "markdown", "--to", "html5", "--standalone",
            "--embed-resources", "--css", TOOLS / "druck.css", "--resource-path", DOCS,
            "--metadata", f"pagetitle={title}", "--metadata", "lang=de-DE", "--output", html,
        )  # fmt: skip
        _run(
            CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
            f"--user-data-dir={Path(work) / 'chrome'}", f"--print-to-pdf={target}",
            html.as_uri(),
        )  # fmt: skip


def _drop_folder_entries(pptx: Path) -> None:
    """pptxgenjs writes folder entries; some cloud viewers refuse such files."""
    with tempfile.TemporaryDirectory() as work:
        cleaned = Path(work) / pptx.name
        with zipfile.ZipFile(pptx) as source, zipfile.ZipFile(cleaned, "w") as target:
            for item in source.infolist():
                if not item.filename.endswith("/"):
                    target.writestr(item, source.read(item.filename))
        shutil.move(cleaned, pptx)


def build_presentation() -> None:
    _require("node")
    if not (TOOLS / "node_modules" / "pptxgenjs").is_dir():
        _run("npm", "ci", "--prefix", TOOLS)
    _run("node", TOOLS / "praesentation.cjs")
    _drop_folder_entries(PRESENTATION_PPTX)
    PRESENTATION_PDF.parent.mkdir(parents=True, exist_ok=True)
    script = f'''
        tell application "Keynote"
            set deck to open POSIX file "{PRESENTATION_PPTX}"
            delay 2
            export deck to POSIX file "{PRESENTATION_PDF}" as PDF with properties ¬
                {{PDF image quality:Best}}
            close deck saving no
        end tell
    '''
    _run("osascript", "-e", script)


def main() -> None:
    parser = GermanArgumentParser(description="Office- und PDF-Dokumente in output/ erzeugen.")
    parser.add_argument(
        "--ohne-praesentation", action="store_true", help="PowerPoint und Keynote überspringen"
    )
    arguments = parser.parse_args()
    # platform.system() instead of sys.platform: mypy would treat the rest as unreachable on Linux.
    if platform.system() != "Darwin" or not CHROME.exists():
        sys.exit("Braucht macOS mit Google Chrome (und Keynote für die Präsentation).")
    _require("pandoc")

    build_docx(DOCS / "project-documentation.md", DOCUMENTATION_DOCX)
    build_pdf(DOCS / "project-documentation.md", DOCUMENTATION_PDF, "Projektdokumentation")
    build_pdf(DOCS / "presentation-speaker-notes.md", SPEAKER_NOTES_PDF, "Sprechertext")
    if not arguments.ohne_praesentation:
        build_presentation()
    for path in (DOCUMENTATION_DOCX, DOCUMENTATION_PDF, SPEAKER_NOTES_PDF, PRESENTATION_PPTX,
                 PRESENTATION_PDF):  # fmt: skip
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
