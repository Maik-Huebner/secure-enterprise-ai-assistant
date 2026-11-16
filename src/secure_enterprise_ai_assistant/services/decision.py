"""Rule-based decision support (NB-GDE-001 §4). It recommends; it never decides."""

from __future__ import annotations

from collections.abc import Sequence

from secure_enterprise_ai_assistant.models.domain import (
    ComplianceFinding,
    ComplianceRule,
    DecisionRecommendation,
)
from secure_enterprise_ai_assistant.models.tools import DecisionSummary


class DecisionService:
    """Derive a recommendation from rule results; hard-decline flags live in the ruleset."""

    def __init__(self, rules: Sequence[ComplianceRule]) -> None:
        self._hard = {rule.rule_id for rule in rules if rule.hard_decline}

    def summarize(self, findings: Sequence[ComplianceFinding]) -> DecisionSummary:
        failed = [finding.rule_id for finding in findings if not finding.passed]
        hard = [rule_id for rule_id in failed if rule_id in self._hard]
        if hard:
            recommendation = DecisionRecommendation.DECLINE
            rationale = "Mindestens ein nicht behebbares hartes Ablehnungskriterium ist verletzt."
        elif failed:
            recommendation = DecisionRecommendation.MANUAL_REVIEW
            rationale = "Mindestens eine Warnung oder behebbare Nachweislücke ist offen."
        else:
            recommendation = DecisionRecommendation.APPROVE
            rationale = "Alle maschinenlesbaren Prüfregeln wurden bestanden."
        return DecisionSummary(
            recommendation=recommendation,
            rationale=rationale,
            failed_rules=failed,
            hard_decline_rules=hard,
        )
