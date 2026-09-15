"""Allowlisted, rule-driven NovaBank compliance evaluation."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from secure_enterprise_ai_assistant.models.domain import (
    ComplianceFinding,
    ComplianceRule,
    CreditCase,
    DocumentStatus,
    EmploymentStatus,
)
from secure_enterprise_ai_assistant.services.errors import ComplianceConfigurationError
from secure_enterprise_ai_assistant.services.financial_analysis import FinancialAnalysisService

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[3] / "data" / "compliance" / "rules.json"

RuleEvaluator = Callable[[CreditCase, ComplianceRule], tuple[bool, str]]


class ComplianceService:
    """Evaluate validated cases with versioned, machine-readable policy rules."""

    def __init__(
        self,
        rules: list[ComplianceRule],
        financial_service: FinancialAnalysisService | None = None,
    ) -> None:
        self._rules = tuple(rules)
        self._financial_service = financial_service or FinancialAnalysisService()
        self._evaluators: dict[str, RuleEvaluator] = {
            "kyc_not_in": self._kyc_not_in,
            "kyc_equals": self._kyc_equals,
            "required_documents_present": self._required_documents_present,
            "all_documents_valid": self._all_documents_valid,
            "dti_at_most": self._dti_at_most,
            "risk_class_in": self._risk_class_in,
            "temporary_employment_months": self._temporary_employment_months,
            "amount_at_most": self._amount_at_most,
            "term_at_most": self._term_at_most,
        }
        unknown = {
            str(rule.parameters.get("predicate")) for rule in rules
        } - self._evaluators.keys()
        if unknown:
            raise ComplianceConfigurationError(
                f"Ruleset contains non-allowlisted predicates: {sorted(unknown)}"
            )

    @classmethod
    def from_json(cls, path: Path = DEFAULT_RULES_PATH) -> ComplianceService:
        """Load a local ruleset and validate every rule against the domain schema."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise ComplianceConfigurationError(f"Cannot load compliance rules: {path}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
            raise ComplianceConfigurationError("Compliance ruleset must contain a 'rules' list.")
        try:
            rules = TypeAdapter(list[ComplianceRule]).validate_python(payload["rules"])
        except ValidationError as exc:
            raise ComplianceConfigurationError(
                "Compliance rules failed schema validation."
            ) from exc
        return cls(rules)

    def check(self, case: CreditCase) -> tuple[ComplianceFinding, ...]:
        """Return one transparent pass/fail finding per configured rule."""
        findings = []
        for rule in self._rules:
            predicate = str(rule.parameters["predicate"])
            passed, detail = self._evaluators[predicate](case, rule)
            findings.append(
                ComplianceFinding(
                    rule_id=rule.rule_id,
                    passed=passed,
                    severity=rule.severity,
                    message=f"{rule.title}: {detail}",
                )
            )
        return tuple(findings)

    @staticmethod
    def _csv_parameter(rule: ComplianceRule, name: str) -> set[str]:
        return {item.strip() for item in str(rule.parameters[name]).split(",")}

    def _kyc_not_in(self, case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        blocked = self._csv_parameter(rule, "statuses")
        actual = case.customer.kyc_status.value
        passed = actual not in blocked
        return passed, f"KYC status is {actual}."

    @staticmethod
    def _kyc_equals(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        expected = str(rule.parameters["status"])
        actual = case.customer.kyc_status.value
        return actual == expected, f"KYC status is {actual}; required status is {expected}."

    def _required_documents_present(
        self, case: CreditCase, rule: ComplianceRule
    ) -> tuple[bool, str]:
        required = self._csv_parameter(rule, "document_types")
        present = {
            item.document_type
            for item in case.documents
            if item.status == DocumentStatus.PRESENT
        }
        missing = sorted(required - present)
        return not missing, "All mandatory documents are present." if not missing else (
            f"Missing or unusable mandatory documents: {', '.join(missing)}."
        )

    @staticmethod
    def _all_documents_valid(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        del rule
        invalid = sorted(
            item.document_type
            for item in case.documents
            if item.status in {DocumentStatus.EXPIRED, DocumentStatus.INVALID}
        )
        return not invalid, "No expired or invalid documents found." if not invalid else (
            f"Expired or invalid documents: {', '.join(invalid)}."
        )

    def _dti_at_most(self, case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        maximum = Decimal(str(rule.parameters["maximum_pct"]))
        actual = self._financial_service.analyze(case).debt_to_income_after_pct
        return actual <= maximum, f"Post-loan DTI is {actual}% (maximum {maximum}%)."

    def _risk_class_in(self, case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        allowed = self._csv_parameter(rule, "classes")
        actual = case.customer.risk_class.value
        return actual in allowed, f"Risk class is {actual}; eligible classes are {sorted(allowed)}."

    @staticmethod
    def _temporary_employment_months(
        case: CreditCase, rule: ComplianceRule
    ) -> tuple[bool, str]:
        minimum = int(rule.parameters["minimum_months"])
        if case.customer.employment_status != EmploymentStatus.TEMPORARY:
            return True, "Employment is not temporary; rule is not applicable."
        actual = case.customer.months_employed
        return actual >= minimum, f"Temporary employment continuity is {actual} months."

    @staticmethod
    def _amount_at_most(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        maximum = Decimal(str(rule.parameters["maximum_eur"]))
        actual = case.application.requested_amount_eur
        return actual <= maximum, f"Requested amount is EUR {actual} (maximum EUR {maximum})."

    @staticmethod
    def _term_at_most(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        maximum = int(rule.parameters["maximum_months"])
        actual = case.application.term_months
        return actual <= maximum, f"Requested term is {actual} months (maximum {maximum})."
