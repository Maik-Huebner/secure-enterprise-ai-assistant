"""Allowlisted, rule-driven NovaBank compliance evaluation."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from secure_enterprise_ai_assistant.core.labels import format_eur, format_pct, label
from secure_enterprise_ai_assistant.models.domain import (
    ComplianceFinding,
    ComplianceRule,
    CreditCase,
    DocumentStatus,
    EmploymentStatus,
)
from secure_enterprise_ai_assistant.resources import RULES_PATH
from secure_enterprise_ai_assistant.services.errors import ComplianceConfigurationError
from secure_enterprise_ai_assistant.services.financial_analysis import FinancialAnalysisService

DEFAULT_RULES_PATH = RULES_PATH

RuleEvaluator = Callable[[CreditCase, ComplianceRule], tuple[bool, str]]
REQUIRED_PARAMETERS: dict[str, frozenset[str]] = {
    "kyc_not_in": frozenset({"statuses"}),
    "kyc_equals": frozenset({"status"}),
    "required_documents_present": frozenset({"document_types"}),
    "all_documents_valid": frozenset(),
    "dti_at_most": frozenset({"maximum_pct"}),
    "risk_class_in": frozenset({"classes"}),
    "temporary_employment_months": frozenset({"minimum_months"}),
    "amount_at_most": frozenset({"maximum_eur"}),
    "term_at_most": frozenset({"maximum_months"}),
}


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
        rule_ids = [rule.rule_id for rule in rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ComplianceConfigurationError("Das Regelwerk enthält doppelte Regel-IDs.")
        predicates = {str(rule.parameters.get("predicate")) for rule in rules}
        unknown = predicates - self._evaluators.keys()
        if unknown:
            raise ComplianceConfigurationError(
                f"Das Regelwerk enthält nicht freigegebene Prüffunktionen: {sorted(unknown)}"
            )
        for rule in rules:
            predicate = str(rule.parameters["predicate"])
            missing = REQUIRED_PARAMETERS[predicate] - rule.parameters.keys()
            if missing:
                raise ComplianceConfigurationError(
                    f"{rule.rule_id}: erforderliche Parameter fehlen: {sorted(missing)}"
                )

    @classmethod
    def from_json(cls, path: Path = DEFAULT_RULES_PATH) -> ComplianceService:
        """Load a local ruleset and validate every rule against the domain schema."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ComplianceConfigurationError(
                "Die Compliance-Regeln fehlen in der Installation."
            ) from exc
        except json.JSONDecodeError as exc:
            raise ComplianceConfigurationError(
                "Die Compliance-Regeln sind kein gültiges JSON."
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
            raise ComplianceConfigurationError(
                "Das Compliance-Regelwerk muss eine Liste 'rules' enthalten."
            )
        try:
            rules = TypeAdapter(list[ComplianceRule]).validate_python(payload["rules"])
        except ValidationError as exc:
            raise ComplianceConfigurationError(
                "Die Compliance-Regeln entsprechen nicht dem Schema."
            ) from exc
        return cls(rules)

    @property
    def rules(self) -> tuple[ComplianceRule, ...]:
        return self._rules

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
                    source_document_id=rule.source_document.split(" ", 1)[0],
                    source_section=rule.source_section,
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
        return passed, f"KYC-Status ist {label(actual)}."

    @staticmethod
    def _kyc_equals(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        expected = str(rule.parameters["status"])
        actual = case.customer.kyc_status.value
        return actual == expected, (
            f"KYC-Status ist {label(actual)}; erforderlich ist {label(expected)}."
        )

    def _required_documents_present(
        self, case: CreditCase, rule: ComplianceRule
    ) -> tuple[bool, str]:
        required = self._csv_parameter(rule, "document_types")
        present = {
            item.document_type for item in case.documents if item.status == DocumentStatus.PRESENT
        }
        missing = sorted(required - present)
        return not missing, "Alle Pflichtunterlagen liegen vor." if not missing else (
            "Fehlende oder unbrauchbare Pflichtunterlagen: "
            f"{', '.join(label(item) for item in missing)}."
        )

    @staticmethod
    def _all_documents_valid(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        del rule
        invalid = sorted(
            item.document_type
            for item in case.documents
            if item.status in {DocumentStatus.EXPIRED, DocumentStatus.INVALID}
        )
        return (
            not invalid,
            "Keine abgelaufenen oder ungültigen Unterlagen gefunden."
            if not invalid
            else (
                "Abgelaufene oder ungültige Unterlagen: "
                f"{', '.join(label(item) for item in invalid)}."
            ),
        )

    def _dti_at_most(self, case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        maximum = Decimal(str(rule.parameters["maximum_pct"]))
        actual = self._financial_service.analyze(case).debt_to_income_after_pct
        return actual <= maximum, (
            f"DTI nach Kredit beträgt {format_pct(actual)} (Höchstwert {format_pct(maximum)})."
        )

    def _risk_class_in(self, case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        allowed = self._csv_parameter(rule, "classes")
        actual = case.customer.risk_class.value
        return actual in allowed, (
            f"Risikoklasse ist {actual}; zulässig sind {', '.join(sorted(allowed))}."
        )

    @staticmethod
    def _temporary_employment_months(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        minimum = int(rule.parameters["minimum_months"])
        if case.customer.employment_status != EmploymentStatus.TEMPORARY:
            return True, "Die Beschäftigung ist nicht befristet; die Regel ist nicht anwendbar."
        actual = case.customer.months_employed
        return actual >= minimum, (
            f"Die befristete Beschäftigung besteht seit {actual} Monaten "
            f"(Mindestdauer {minimum} Monate)."
        )

    @staticmethod
    def _amount_at_most(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        maximum = Decimal(str(rule.parameters["maximum_eur"]))
        actual = case.application.requested_amount_eur
        return actual <= maximum, (
            f"Beantragter Betrag ist {format_eur(actual)} (Höchstwert {format_eur(maximum)})."
        )

    @staticmethod
    def _term_at_most(case: CreditCase, rule: ComplianceRule) -> tuple[bool, str]:
        maximum = int(rule.parameters["maximum_months"])
        actual = case.application.term_months
        return actual <= maximum, (
            f"Beantragte Laufzeit beträgt {actual} Monate (Höchstwert {maximum} Monate)."
        )
