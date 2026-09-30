"""Unit tests for synthetic case lookup behavior."""

import json

import pytest

from secure_enterprise_ai_assistant.development.synthetic_data import build_dataset
from secure_enterprise_ai_assistant.services.case_repository import CustomerCaseRepository
from secure_enterprise_ai_assistant.services.errors import (
    CaseNotFoundError,
    CustomerNotFoundError,
    DatasetError,
)


@pytest.fixture
def repository() -> CustomerCaseRepository:
    cases, _ = build_dataset()
    return CustomerCaseRepository(cases)


def test_get_case_and_customer(repository: CustomerCaseRepository) -> None:
    case = repository.get_case("CASE-00001")

    assert case == repository.get_by_customer_id(case.customer.customer_id)
    assert len(repository.list_cases()) == 48


def test_unknown_ids_raise_safe_errors(repository: CustomerCaseRepository) -> None:
    with pytest.raises(CaseNotFoundError, match="CASE-99999"):
        repository.get_case("CASE-99999")
    with pytest.raises(CustomerNotFoundError, match="C-99999"):
        repository.get_by_customer_id("C-99999")


def test_invalid_json_dataset_is_rejected(tmp_path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": [{"not": "a case"}]}), encoding="utf-8")

    with pytest.raises(DatasetError, match="domain validation"):
        CustomerCaseRepository.from_json(path)
