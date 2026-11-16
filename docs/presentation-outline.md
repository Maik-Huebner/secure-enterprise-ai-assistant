# Präsentationsstruktur: Secure Enterprise AI Assistant

> **Historischer Stand (v1.0.2, Abschlussprojekt).** Dieses Dokument beschreibt die erste Version mit CrewAI und einem 24B-Mistral-Profil. Beides wurde in v1.4 durch einen LangGraph-Workflow mit einem lokalen 9B-Modell ersetzt. Aktuell gelten [README](../README.md) und [Architektur](architecture.md).

Zielzeit: **9:20 Minuten**. Die Präsentation besteht aus neun Folien und lässt rund 40 Sekunden Reserve im 10-Minuten-Fenster.

## Folie 1: Secure Enterprise AI Assistant

**Sichtbare Inhalte**

- Lokaler Enterprise-KI-Assistent für eine fiktive Bank
- NovaBank Financial Services AG ist vollständig fiktiv
- Alle Fälle, Regeln und Richtlinien sind synthetisch
- Release `v1.0.2`

**Visual:** `assets/ui-overview.png` groß auf der rechten Folienhälfte.

**Zielzeit:** 0:45 Minuten

**Kernaussage:** Das Projekt demonstriert einen lokalen, nachvollziehbaren KI-Assistenten ohne reale Kunden- oder Bankdaten.

## Folie 2: Problem und Projektziel

**Sichtbare Inhalte**

- Strukturierte Falldaten und unstrukturierte Policies zusammenführen
- Finanzwerte reproduzierbar statt probabilistisch berechnen
- Compliance-Regeln vollständig prüfen
- Quellen und Tool-Nutzung sichtbar belegen
- Lokale Verarbeitung und kontrollierte MCP-Zugriffe

**Visual:** Zweispaltige Gegenüberstellung von fachlichem Risiko und technischer Projektantwort.

**Zielzeit:** 0:55 Minuten

**Kernaussage:** Ein einfacher Chatbot reicht für kreditnahe Abläufe nicht aus; Fakten, Regeln und Quellen benötigen kontrollierte Komponenten.

## Folie 3: Vollständig synthetische Datenbasis

**Sichtbare Inhalte**

- 48 fiktive Kreditfälle
- Fiktive Kundenprofile und Kreditanträge
- 18 interne Richtlinien und Wissensdokumente
- Versionierte Compliance-Regeln
- Synthetische Ground Truth für Evaluation

**Visual:** Vier große Kennzahlen und ein klarer Hinweis „Keine realen Kunden- oder Bankdaten“.

**Zielzeit:** 0:50 Minuten

**Kernaussage:** Die gesamte Demonstration basiert auf reproduzierbaren, eigens erzeugten Testdaten.

## Folie 4: Was kann das System?

**Sichtbare Inhalte**

- Kundenfälle strukturiert zusammenfassen
- Finanzkennzahlen deterministisch berechnen
- Compliance-Regeln mit Policy-Evidenz prüfen
- Wissensbasis per RAG durchsuchen
- Verifizierte Entscheidungsvorlagen erzeugen

**Visual:** `assets/ui-financial-analysis.png` mit Fokus auf deutsche Kennzahlen und Routing-Informationen.

**Zielzeit:** 1:10 Minuten

**Kernaussage:** Natürliche Anfragen führen zu überprüfbaren Ergebnissen aus klar getrennten Fachfähigkeiten.

## Folie 5: Systemarchitektur

**Sichtbare Inhalte**

- Gradio UI und deterministisches Intent Routing
- Model Router mit `fast_local` und `complex_agentic`
- CrewAI oder verifizierter MCP-Pfad
- Echter MCP-stdio-Transport zu vier FastMCP-Tools
- Eigene Services für Fälle, Finanzlogik, Compliance und RAG

**Visual:** Zentrales Architekturdiagramm mit klarer Tool-Grenze und beiden Modellprofilen.

**Zielzeit:** 1:15 Minuten

**Kernaussage:** Sprachmodelle orchestrieren und erklären; strukturierte Services liefern die fachlichen Fakten.

## Folie 6: NLP und Generative AI im Projekt

**Sichtbare Inhalte**

- Ollama, lokale LLMs und Prompt Engineering
- RAG mit Chunking, Embeddings, FAISS, BM25S und Hybrid Retrieval
- Agentic AI mit CrewAI, CrewAI Flows und Tool Use
- MCP/FastMCP, Pydantic, Guardrails, Gradio und Evaluation
- Nicht verwendet: **LangChain** und **LangGraph**

**Visual:** Technologieübersicht links und `assets/ui-rag-sources.png` rechts als Quellenbeleg.

**Zielzeit:** 1:10 Minuten

**Kernaussage:** Die Kursinhalte sind direkt im eigenen Stack umgesetzt; LangChain und LangGraph gehören nicht zur finalen Architektur.

## Folie 7: Praxisbeispiel CASE-00031

**Sichtbare Inhalte**

- Monatliche Rate: **570,64 EUR**
- DTI nach Finanzierung: **44,95 %**
- Gesamtzins: **5.488,40 EUR**
- `RULE-005`: `FAIL`
- Empfehlung: `MANUAL REVIEW`

**Visual:** `assets/ui-full-assessment-report.png` groß mit sichtbarem Report und Policy-Kontext.

**Zielzeit:** 1:20 Minuten

**Kernaussage:** Full Assessment verbindet Fall, Financial Engine, Compliance und RAG zu einer belegten Entscheidungsvorlage.

## Folie 8: Qualität, Guardrails und Demo-Safe-Modus

**Sichtbare Inhalte**

- 84 automatisierte Tests und erfolgreiche CI
- 8 synthetische Offline-Metriken mit Wert 1,0
- `verified_mcp` ruft alle vier MCP-Werkzeuge auf
- Transparenter Modus `deterministic_mcp_fallback`
- Gemessene lokale Laufzeit: rund **1,034 Sekunden**

**Visual:** `assets/ui-execution-trace.png` mit Modellprofil, Safe-Mode-Grund und Werkzeugliste.

**Zielzeit:** 1:10 Minuten

**Kernaussage:** Der verifizierte Demo-Pfad ist reproduzierbar, transparent und verschleiert den übersprungenen Mistral-Lauf nicht.

## Folie 9: Fazit und Grenzen

**Sichtbare Inhalte**

- Generative AI plus deterministische Fachsysteme
- Agentic AI, RAG und MCP im lokalen Betrieb
- Nachvollziehbare Quellen, Regeln und Ausführung
- Prototyp mit synthetischen Daten, kein Produktivsystem
- Nächste Schritte: reale Validierung, Security Review und Human Oversight

**Visual:** Reduzierte Abschlussfolie mit den vier Bausteinen „Local First“, „Agentic AI“, „MCP-Evidenz“ und „deterministische Fachlogik“.

**Zielzeit:** 0:45 Minuten

**Kernaussage:** Der Prototyp belegt die technische Integration, behauptet aber weder reale Bankenentscheidung noch regulatorische Produktionsreife.

## Zeitplan

| Folie | Dauer |
|---|---:|
| 1. Projektübersicht | 0:45 |
| 2. Problem und Ziel | 0:55 |
| 3. Fiktive Datenbasis | 0:50 |
| 4. Systemfähigkeiten | 1:10 |
| 5. Architektur | 1:15 |
| 6. NLP und Generative AI | 1:10 |
| 7. CASE-00031 | 1:20 |
| 8. Qualität und Safe Mode | 1:10 |
| 9. Fazit | 0:45 |
| **Gesamt** | **9:20** |
