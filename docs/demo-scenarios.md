# Demo-Szenarien (ab v1.4)

Alle Fälle und Richtlinien sind synthetisch. Für die Demo zwei Benutzer anlegen, zum Beispiel
`anna.becker` und `tom.klein` mit der Rolle `pruefer`, sowie `max.muster` als `sachbearbeiter`
in `team-nord` (siehe README, „Local setup“).

## 1 – Wissensfrage mit Quellen

Frage: `Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?`

Erwartet: Route `knowledge`, Werkzeug `search_internal_knowledge`, Antwort des Modells mit
Quelle `NB-DOC-001`, Abschnitt 3.1, Ausführungsmodus `llm_grounded`.

## 2 – Frage ohne Antwort in den Richtlinien

Frage: `Wie hoch ist der Dispozins für ein Girokonto?`

Erwartet: keine passende Quelle, Modus `no_answer`, **kein** Modellaufruf. Das System sagt, dass
die Richtlinien die Frage nicht beantworten, statt etwas zu erfinden.

## 3 – Deterministische Finanzanalyse

Frage: `Berechne die Kreditbelastung für CASE-00001.`

Erwartet: Monatsrate 419,46 EUR, DTI 4,00 % → 10,71 %. Alle Zahlen kommen aus
`analyze_financial_case`; die Antwortprüfung lehnt jede Zahl ab, die nicht in den Nachweisen
steht.

## 4 – Compliance-Problem

Frage: `Welche Compliance-Probleme hat CASE-00017?`

Erwartet: `RULE-003` nicht bestanden (Einkommensnachweis fehlt), Quelle `NB-DOC-001`.

## 5 – Entscheidungsvorlage mit Vier-Augen-Freigabe

Frage (als `anna.becker`): `Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage.`

Erwartet: Vorlage ohne Sprachmodell, Empfehlung „Manuelle Prüfung“ wegen `RULE-005`
(DTI nach Kredit 44,95 % über der Prüfschwelle 40 %), Status `awaiting_approval`.
Im Reiter „Freigaben“ kann `anna.becker` die eigene Vorlage **nicht** freigeben; `tom.klein`
kann freigeben oder ablehnen.

Zum Vergleich eindeutig problematische Fälle: `CASE-00007` (DTI über der harten Grenze von 50 %)
oder `CASE-00008` (KYC abgelehnt, Risikoklasse E) – beide mit Empfehlung „Ablehnung“.

## 6 – Rechte

Als `max.muster` (Team Nord): `Zeige CASE-00031.` → „nicht gefunden“, genau wie bei einer
unbekannten Fall-ID, weil Fall 31 zu Team Süd gehört. Eine Entscheidungsvorlage darf die Rolle
`sachbearbeiter` nicht anfordern.
