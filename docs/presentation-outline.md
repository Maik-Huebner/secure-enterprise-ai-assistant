# Präsentationsstruktur: Secure Enterprise AI Assistant (v2.1)

Zielzeit: **9:15 Minuten** für zehn Folien, rund 45 Sekunden Reserve im 10-Minuten-Fenster. Die
Sprechtexte stehen in [presentation-speaker-notes.md](presentation-speaker-notes.md) und als
Notizen in der PowerPoint-Datei. Alle Zahlen stammen aus echten Läufen (README, `reports/`).

## Folie 1: Secure Enterprise AI Assistant

- Lokale Entscheidungsunterstützung für Kreditfälle einer fiktiven Bank
- NovaBank Financial Services AG, alle Daten synthetisch
- Release v2.1.0, MacBook Pro M4 Pro, `qwen3.5:9b`

**Bild:** `assets/ui-v2-assistant.jpg` · **Zeit:** 0:40 · **Kernaussage:** Ein lokaler
KI-Assistent, dessen Fakten man nachprüfen kann.

## Folie 2: Fakten aus Code, Sprache aus dem Modell

- Links: Risiken eines reinen Chatbots (verrechnet sich, übersieht Regeln, erfindet Quellen)
- Rechts: Antwort des Projekts (Rechner und Regelwerk hinter MCP, Quellenpflicht, Antwortprüfung,
  Freigabe durch einen Menschen)

**Zeit:** 0:55 · **Kernaussage:** Das Modell formuliert nur; Fakten und Entscheidungen liegen
woanders.

## Folie 3: Von v1 zu v2

- Prüfbericht von v1.0.2 als Ausgangspunkt, neun Pakete mit Tag und Lernnotiz
- Zahlen: Recall@5 0,75 → 1,00; Eingabefilter 1/12 → 15/20 im Holdout; CrewAI und 24B → LangGraph
  und 9B; keine Anmeldung → JWT, Rollen, Audit-Log

**Zeit:** 0:55 · **Kernaussage:** Jede Verbesserung ist gemessen, nicht behauptet.

## Folie 4: Architektur

**Bild:** `assets/architektur-v2.png` · **Zeit:** 1:05 · **Kernaussage:** Der Router legt die
Werkzeuge fest, das Modell wählt keine („Least Agency“); Rechte werden dreimal geprüft.

## Folie 5: Suche und Routing

- Diagramm: MRR im Testteil für Hashing, bge-m3, qwen3-embedding:0.6b, embeddinggemma
- Hybrid aus Vektoren, BM25 und Kennungen, Filter vor dem Ranking, „keine Antwort“ statt Raten
- Hybrider Router: 24/24 im Testteil, 8 ms, kein Sprachmodell

**Zeit:** 0:55 · **Kernaussage:** Gute Suche ist gemessen und rechtebewusst.

## Folie 6: Antwortprüfung und Vier-Augen-Freigabe

- Ablauf: Antwort → Prüfung → zweiter Versuch → verifizierter Rückfallweg
- Vorlage ohne Modell → Pause → zweite Person gibt frei

**Bild:** `assets/ui-v2-approval.jpg` · **Zeit:** 1:00 · **Kernaussage:** Kein ungeprüfter Satz
und keine Selbstfreigabe.

## Folie 7: Praxisbeispiel CASE-00031

- Rate 570,64 EUR, DTI 28,41 % → 44,95 %, Gesamtzins 5.488,40 EUR
- `RULE-005` nicht bestanden (Prüfschwelle 40 %), neun Regeln bestanden → manuelle Prüfung
- Selbstfreigabe abgewiesen, zweite Person gibt frei

**Zeit:** 0:55 · **Kernaussage:** Vom Fall zur geprüften Vorlage in einem nachvollziehbaren Ablauf.

## Folie 8: Sicherheit

- Rollen und Team-Rechte, fremde Fälle wie unbekannte
- eigenes MCP-Token pro Lauf, kein Token Passthrough
- Eingabefilter, Dokumente als Daten, Audit-Log mit Hash-Kette, alles lokal

**Zeit:** 0:55 · **Kernaussage:** Rechte gehören in den Code, nicht in den Prompt.

## Folie 9: Qualität ehrlich gemessen

- Antwortqualität Lauf 3: 13/15 Fakten, 2/2 richtig abgelehnt, 11/14 belegt per Handprüfung
- Mit Suche 8/10 Richtlinienfragen, ohne Suche 1/10
- 321 Tests + 4 Live-Tests, Langfuse-Experiment

**Zeit:** 1:00 · **Kernaussage:** Die Zahlen sind gut, aber ehrlich eingeordnet.

## Folie 10: Fazit und Grenzen

- Was es zeigt: Least Agency, prüfbare Antworten, menschliche Freigabe, alles lokal und deutsch
- Grenzen: synthetische Daten, kein Identity Provider, kleine Testsammlungen
- Nächste Schritte: Reranker, unabhängige Testsätze, Identity Provider

**Zeit:** 0:45 · **Kernaussage:** Ein ehrlicher, nachprüfbarer Prototyp, kein Bankprodukt.

## Zeitplan

| Folie | Zeit | Summe |
|---:|---:|---:|
| 1 | 0:40 | 0:40 |
| 2 | 0:55 | 1:35 |
| 3 | 0:55 | 2:30 |
| 4 | 1:05 | 3:35 |
| 5 | 0:55 | 4:30 |
| 6 | 1:00 | 5:30 |
| 7 | 0:55 | 6:25 |
| 8 | 0:55 | 7:20 |
| 9 | 1:00 | 8:20 |
| 10 | 0:45 | 9:05 |
