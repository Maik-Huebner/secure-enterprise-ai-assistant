"""Read-only repository for validated synthetic NovaBank credit cases."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from secure_enterprise_ai_assistant.models.domain import CreditCase
from secure_enterprise_ai_assistant.resources import CASES_PATH
from secure_enterprise_ai_assistant.services.errors import (
    CaseNotFoundError,
    CustomerNotFoundError,
    DatasetError,
)

DEFAULT_CASES_PATH = CASES_PATH


class CustomerCaseRepository:
    """Provide indexed access without exposing evaluation-only decision labels."""

    def __init__(self, cases: Iterable[CreditCase]) -> None:
        validated_cases = list(cases)
        self._by_case_id = {case.case_id: case for case in validated_cases}
        self._by_customer_id = {case.customer.customer_id: case for case in validated_cases}
        if len(self._by_case_id) != len(validated_cases):
            raise DatasetError("Der synthetische Datensatz enthält doppelte Fall-IDs.")
        if len(self._by_customer_id) != len(validated_cases):
            raise DatasetError("Der synthetische Datensatz enthält doppelte Kunden-IDs.")

    @classmethod
    def from_json(cls, path: Path = DEFAULT_CASES_PATH) -> CustomerCaseRepository:
        """Load and validate the versioned JSON dataset."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise DatasetError("Der synthetische Falldatensatz fehlt in der Installation.") from exc
        except json.JSONDecodeError as exc:
            raise DatasetError(
                f"Der synthetische Falldatensatz ist kein gültiges JSON: {path}"
            ) from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
            raise DatasetError("Der synthetische Falldatensatz muss eine Liste 'cases' enthalten.")
        try:
            cases = TypeAdapter(list[CreditCase]).validate_python(payload["cases"])
        except ValidationError as exc:
            raise DatasetError(
                "Der synthetische Falldatensatz entspricht nicht dem Fachmodell."
            ) from exc
        return cls(cases)

    def get_case(self, case_id: str) -> CreditCase:
        """Return one case or raise a domain-specific error."""
        try:
            return self._by_case_id[case_id]
        except KeyError as exc:
            raise CaseNotFoundError(f"Unbekannte synthetische Fall-ID: {case_id}") from exc

    def get_by_customer_id(self, customer_id: str) -> CreditCase:
        """Return the case associated with one synthetic customer."""
        try:
            return self._by_customer_id[customer_id]
        except KeyError as exc:
            raise CustomerNotFoundError(
                f"Unbekannte synthetische Kunden-ID: {customer_id}"
            ) from exc

    def list_cases(self) -> tuple[CreditCase, ...]:
        """Return cases in stable case-ID order."""
        return tuple(self._by_case_id[key] for key in sorted(self._by_case_id))
