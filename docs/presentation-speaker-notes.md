# Sprechernotizen: Secure Enterprise AI Assistant

Die Texte sind für eine ruhige Sprechgeschwindigkeit geplant. Regiehinweise in eckigen Klammern werden nicht vorgelesen.

## Folie 1: Secure Enterprise AI Assistant

**Zielzeit:** 0:45 Minuten

Guten Tag. Ich stelle den Secure Enterprise AI Assistant vor, einen lokalen Enterprise-KI-Assistenten für die vollständig fiktive NovaBank Financial Services AG. Das Projekt zeigt, wie generative KI mit strukturierten Daten, Unternehmenswissen, deterministischen Berechnungen und kontrolliertem Tool-Zugriff verbunden werden kann. Alle 48 Kreditfälle, Kundenprofile, Anträge, Regeln und 18 internen Richtlinien wurden eigens für den Demonstrator synthetisch erstellt. Es werden keine realen Kunden- oder Bankdaten verarbeitet. Der gezeigte Stand entspricht Release `v1.0.2`.

## Folie 2: Problem und Projektziel

**Zielzeit:** 0:55 Minuten

Bei einer Kreditprüfung kommen unterschiedliche Informationsarten zusammen: strukturierte Falldaten, mathematische Kennzahlen, interne Regeln und unstrukturierte Richtlinien. Ein einfacher Chatbot kann diese Inhalte formulieren, liefert allein aber keine verlässliche Fachlogik. Besonders kritisch wären frei berechnete Finanzwerte, ausgelassene Regeln oder erfundene Schwellenwerte. Das Projektziel war deshalb eine klare Trennung. Das Sprachmodell erklärt und strukturiert. Die Financial Engine rechnet, die Compliance Engine prüft Regeln und das RAG-System liefert belegte Policy-Aussagen. Jeder fachliche Zugriff läuft kontrolliert über MCP und wird im Ausführungsprotokoll sichtbar.

## Folie 3: Vollständig synthetische Datenbasis

**Zielzeit:** 0:50 Minuten

Die Datenbasis wurde vollständig für das Projekt erzeugt. Sie umfasst 48 fiktive Kreditfälle mit Kundenprofilen, Kreditanträgen und Dokumentstatus. Hinzu kommen 18 versionierte interne Richtlinien sowie ein strukturiertes Compliance-Regelwerk. Eine getrennte synthetische Ground Truth ermöglicht reproduzierbare Tests und Evaluationen. Stabile Demonstrationsfälle decken positive Entscheidungen, fehlende Dokumente und erhöhte Verschuldung ab. Diese Trennung ist wichtig: Evaluationslabels gelangen nicht als versteckte Entscheidungsevidenz an die Agents oder an den verifizierten MCP-Bericht.

## Folie 4: Was kann das System?

**Zielzeit:** 1:10 Minuten

Das System unterstützt fünf Anfragetypen. Es kann einen Kundenfall strukturiert zusammenfassen, finanzielle Kennzahlen berechnen, Compliance-Regeln prüfen, die interne Wissensbasis durchsuchen und alle Ergebnisse zu einer Entscheidungsvorlage verbinden. Im gezeigten Beispiel fragt der Nutzer auf Deutsch nach der finanziellen Belastung für `CASE-00031`. Der Router wählt das Profil `fast_local` mit `qwen3.5:9b`. CrewAI lädt den Fall und ruft die Financial Engine über MCP auf. Die Antwort nennt 570,64 Euro monatliche Rate, den DTI-Anstieg von 28,41 auf 44,95 Prozent sowie Gesamtzins und Gesamtrückzahlung. Die Zahlen stammen unverändert aus dem deterministischen Werkzeug.

## Folie 5: Systemarchitektur

**Zielzeit:** 1:15 Minuten

Die Anfrage beginnt in einer deutschsprachigen Gradio-Oberfläche. Der Intent Router wählt deterministisch einen der fünf Workflows. Danach ordnet der Model Router ein Profil zu: `fast_local` mit Qwen für kurze Standardabläufe oder `complex_agentic` mit dem konfigurierten Mistral-Modell für Full Assessment. Einfache Abläufe führt CrewAI aus. Die vollständige Prüfung nutzt im lokalen Standard unmittelbar den verifizierten MCP-Pfad. Beide Wege kommunizieren über echten MCP-stdio-Transport mit FastMCP. Hinter dieser Grenze liegen vier Werkzeuge für Fallabruf, Finanzanalyse, Compliance und Wissenssuche. Kein Agent greift direkt auf die Business Services zu. Dadurch bleiben Orchestrierung, Tool-Transport und Fachlogik getrennt überprüfbar.

## Folie 6: NLP und Generative AI im Projekt

**Zielzeit:** 1:10 Minuten

Aus dem NLP- und Generative-AI-Modul verwendet das Projekt lokale LLMs über Ollama und systematisches Prompt Engineering. Der eigene RAG-Stack umfasst Dokumentaufnahme, Chunking, Embeddings, FAISS, BM25S und Hybrid Retrieval. Agentic AI wird mit CrewAI, CrewAI Flows und kontrolliertem Tool Use umgesetzt. MCP und FastMCP bilden die Werkzeuggrenze. Pydantic stellt strukturierte Ein- und Ausgaben sicher. Hinzu kommen Guardrails, eine Gradio-Oberfläche und eine reproduzierbare Evaluation. LangChain und LangGraph werden weder direkt noch transitiv verwendet. Der sichtbare Quellenbereich zeigt, dass die Wissensantwort konkrete Dokument-IDs und technische Ausführungsdaten behält.

## Folie 7: Praxisbeispiel CASE-00031

**Zielzeit:** 1:20 Minuten

Das Full Assessment verbindet alle vier fachlichen Fähigkeiten. Für `CASE-00031` liefert die Financial Engine eine monatliche Rate von 570,64 Euro. Der DTI steigt von 28,41 auf 44,95 Prozent, der Gesamtzins beträgt 5.488,40 Euro. Die Compliance Engine prüft das vollständige Regelwerk. `RULE-005` schlägt fehl, weil der DTI über der internen synthetischen NovaBank-Review-Schwelle von 40 Prozent liegt. Das ist ausdrücklich keine allgemein behauptete regulatorische Grenze. Die Empfehlung lautet `MANUAL REVIEW`. Ergänzend liefert das RAG-System passende `NB-*`-Quellen. Der Bericht übernimmt die strukturierten Werte unverändert und schließt mit `END OF VERIFIED REPORT`.

## Folie 8: Qualität, Guardrails und Demo-Safe-Modus

**Zielzeit:** 1:10 Minuten

Der Release-Stand umfasst 84 automatisierte Tests und eine erfolgreiche CI. Acht Offline-Metriken erreichen im kontrollierten synthetischen Benchmark jeweils 1,0. Dazu gehört jetzt auch die Genauigkeit der Eingabe-Guardrails auf sechs blockierten und unbedenklichen Testanfragen. Diese Werte zeigen die Konsistenz der Testsuite, nicht die Genauigkeit einer realen Bankentscheidung. Für Full Assessment ist `mistral-small3.2:24b` dem Profil `complex_agentic` zugeordnet. Der native lokale Multi-Agent-Lauf benötigt jedoch mehrere Minuten. Deshalb verwendet die Demo standardmäßig `verified_mcp`. Dieser Pfad öffnet eine echte MCP-stdio-Session, ruft alle vier Werkzeuge auf und erzeugt den Bericht in rund 1,034 Sekunden. Der Trace nennt transparent `deterministic_mcp_fallback` und behauptet keinen ausgeführten Mistral-Lauf.

## Folie 9: Fazit und Grenzen

**Zielzeit:** 0:45 Minuten

Der Prototyp verbindet generative KI mit deterministischer Fachlogik, Agentic AI, RAG und MCP. Lokale Modelle unterstützen die Sprache und Orchestrierung. Kontrollierte Services liefern Fälle, Berechnungen, Regelbefunde und Quellen. Das macht die Ausführung nachvollziehbar und begrenzt unbelegte Aussagen. Gleichzeitig bleiben klare Grenzen: Alle Daten sind synthetisch, der native Mistral-Modus ist experimentell und produktive Authentifizierung, Monitoring sowie regulatorische Validierung fehlen. Vor einem realen Einsatz wären repräsentative Daten, ein umfassendes Security Review und verbindliche menschliche Freigaben notwendig. Vielen Dank.
