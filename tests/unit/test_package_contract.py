"""Contracts for version metadata and packaged runtime resources."""

import os
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

from secure_enterprise_ai_assistant import __version__
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.resources import (
    CASES_PATH,
    EVALUATION_SUITE_PATH,
    KNOWLEDGE_ROOT,
    RULES_PATH,
)
from tests.conftest import REVIEWER

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_version_matches_project_and_distribution_metadata() -> None:
    project = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == project["project"]["version"]
    assert __version__ == version("secure-enterprise-ai-assistant")
    assert project["project"]["requires-python"] == ">=3.13,<3.14"
    assert "Programming Language :: Python :: 3.13" in project["project"]["classifiers"]
    assert "Programming Language :: Python :: 3.11" not in project["project"]["classifiers"]
    assert "Programming Language :: Python :: 3.12" not in project["project"]["classifiers"]


def test_runtime_resources_are_inside_package() -> None:
    package_root = CASES_PATH.parents[2]

    assert all(
        path.is_relative_to(package_root)
        for path in (CASES_PATH, RULES_PATH, KNOWLEDGE_ROOT, EVALUATION_SUITE_PATH)
    )
    assert CASES_PATH.is_file()
    assert RULES_PATH.is_file()
    assert EVALUATION_SUITE_PATH.is_file()
    assert len(list(KNOWLEDGE_ROOT.glob("*.md"))) == 18


def test_default_tool_service_is_independent_of_current_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    service = MCPToolService.build_default()

    assert service.get_customer_case("CASE-00001", principal=REVIEWER).case.case_id == "CASE-00001"
    assert service.search_internal_knowledge(
        "Pflichtnachweise für Verbraucherkredite", principal=REVIEWER
    ).results


def test_crewai_import_uses_configured_runtime_directory(tmp_path) -> None:
    runtime_dir = tmp_path / "runtime-state"
    environment = os.environ.copy()
    environment.pop("CREWAI_STORAGE_DIR", None)
    environment["RUNTIME_DIR"] = str(runtime_dir)
    code = (
        "import os; "
        "import secure_enterprise_ai_assistant.agents.factory; "
        f"assert os.environ['CREWAI_STORAGE_DIR'] == {str(runtime_dir)!r}"
    )

    subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
