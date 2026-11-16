# Beispiel-Abläufe (v1.4, echter lokaler Lauf)

Aufgenommen am 16.11.2026 auf einem MacBook Pro M4 Pro (24 GB) mit `qwen3.5:9b` und
`qwen3-embedding:0.6b` über Ollama, echtem MCP-stdio-Server und SQLite-Checkpointer. Zwei
synthetische prüfende Personen: `anna.becker` und `tom.klein`. Die Protokolle zeigen nur
technische Schritte, nie verborgene Gedanken des Modells. Die Zeiten sind Einzelwerte, keine
Messung; gemessene Werte stehen im README (Abschnitt „Antwortqualität des echten Modells“).

## 1 – Finanzfrage (19,0 s)

Frage: `Berechne die finanzielle Belastung für CASE-00031.`

```text
request_received: Anfrage empfangen
intent_classified: financial_analysis
routing_method: keyword
tools_selected: get_customer_case, analyze_financial_case
model_selected: qwen3.5:9b
answer_verification: bestanden
execution_mode: llm_grounded
workflow_completed: Ablauf abgeschlossen
```

Die Antwort nennt Rate 570,64 EUR, DTI 28,41 % → 44,95 %, Anstieg 16,54 Prozentpunkte und
monatliche Verpflichtungen nach Kredit von 1.550,64 EUR. Alle Zahlen stehen in den Nachweisen.

**Vorher (gleicher Tag, vor der Korrektur):** Das Modell hatte die Summe 980,00 + 570,64 selbst
gerechnet. Die Rechnung war richtig, die Prüfung lehnte sie trotzdem ab, weil die Zahl nicht in
den Nachweisen stand:

```text
answer_verification: 1 Mängel
answer_retry: Versuch 2
answer_verification: 1 Mängel
fallback_reason: Die Modellantwort hat die Prüfung zweimal nicht bestanden; die Antwort wurde
                 aus den strukturierten MCP-Nachweisen erzeugt.
execution_mode: verified_fallback
```

Seitdem liefert `analyze_financial_case` die Summe und den Anstieg in Prozentpunkten selbst.

## 2 – Wissensfrage (7,4 s)

Frage: `Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?`

```text
intent_classified: knowledge
routing_method: rule
tools_selected: search_internal_knowledge
model_selected: qwen3.5:9b
answer_verification: bestanden
execution_mode: llm_grounded
```

Antwort (gekürzt): vier Unterlagen nach `NB-DOC-001`, Abschnitt 3.1 – gültiges
Ausweisdokument (`NB-KYC-001`, Abschnitt 2), aktueller Einkommensnachweis, Kontoauszüge der
letzten 90 Tage, vollständig ausgefülltes Kreditantragsformular.

## 3 – Entscheidungsvorlage mit Vier-Augen-Freigabe (0,7 s)

Frage von `anna.becker`: `Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage.`

```text
intent_classified: full_assessment
tools_selected: get_customer_case, analyze_financial_case, check_compliance,
                search_internal_knowledge
execution_mode: verified_mcp
approval_requested: Wartet auf Freigabe durch eine zweite Person
```

Die Vorlage entsteht ohne Sprachmodell: Empfehlung „Manuelle Prüfung“, weil `RULE-005` nicht
bestanden ist (DTI nach Kredit 44,95 %, Prüfschwelle 40,00 %); alle anderen neun Regeln sind
bestanden. Quellen: `NB-CRD-001`, `NB-CRD-002`, `NB-GDE-001`, `NB-RSK-001`.

`anna.becker` versucht, die eigene Vorlage freizugeben:

```text
AccessDeniedError: Vier-Augen-Prinzip: Freigaben erteilt nur eine zweite prüfende Person.
```

`tom.klein` gibt frei:

```text
approval_requested: Wartet auf Freigabe durch eine zweite Person
approval_refused: Freigabe abgewiesen (Vier-Augen-Prinzip)
approval_decision: Freigegeben
workflow_completed: Ablauf abgeschlossen
```

Der abgewiesene Versuch bleibt im Protokoll sichtbar. Die Vorlage endet mit
„**Freigegeben** von tom.klein am 16.11.2026 15:37 UTC“ und dem Kommentar.
