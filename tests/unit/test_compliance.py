"""Tests for machine-readable NovaBank compliance rules."""

import pytest

from secure_enterprise_ai_assistant.development.synthetic_data import build_dataset
from secure_enterprise_ai_assistant.models.domain import ComplianceRule, ComplianceSeverity
from secure_enterprise_ai_assistant.services.compliance import ComplianceService
from secure_enterprise_ai_assistant.services.errors import ComplianceConfigurationError


def _case(case_id: str):
    cases, _ = build_dataset()
    return next(case for case in cases if case.case_id == case_id)


def test_positive_demo_case_passes_all_rules() -> None:
    findings = ComplianceService.from_json().check(_case("CASE-00001"))

    assert len(findings) == 10
    assert all(finding.passed for finding in findings)


def test_missing_income_document_is_reported() -> None:
    findings = ComplianceService.from_json().check(_case("CASE-00017"))

    required_documents = next(item for item in findings if item.rule_id == "RULE-003")
    assert required_documents.passed is False
    assert "income_statement" in required_documents.message


def test_high_debt_load_breaks_hard_dti_limit() -> None:
    findings = ComplianceService.from_json().check(_case("CASE-00007"))

    hard_dti = next(item for item in findings if item.rule_id == "RULE-006")
    assert hard_dti.passed is False
    assert "Post-loan DTI" in hard_dti.message


def test_rejected_kyc_and_risk_class_are_critical() -> None:
    findings = ComplianceService.from_json().check(_case("CASE-00008"))
    failed_ids = {item.rule_id for item in findings if not item.passed}

    assert {"RULE-001", "RULE-002", "RULE-004", "RULE-007"} <= failed_ids


def test_rule_configuration_requires_predicate_parameters() -> None:
    rule = ComplianceRule(
        rule_id="RULE-999",
        title="Incomplete DTI rule",
        description="Synthetic invalid configuration for a regression test.",
        category="affordability",
        severity=ComplianceSeverity.WARNING,
        parameters={"predicate": "dti_at_most"},
        source_document="NB-TST-001 Test",
        source_section="1",
    )

    with pytest.raises(ComplianceConfigurationError, match="maximum_pct"):
        ComplianceService([rule])
