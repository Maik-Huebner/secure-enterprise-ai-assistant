# Umsetzungsplan v2.0

**Grundlage:** [Prüfbericht v1.0.2](audit-v1.md)
**Status:** Entwurf, wartet auf Freigabe

## Leitlinien für alle Pakete

- Jedes Paket bekommt einen eigenen Branch (`v2/paket-N-…`), kleine Commits und einen Pull Request.
- Weiter geht es erst, wenn CI grün ist und du den PR freigegeben hast.
- Nach jedem Paket: Tag setzen, Lernnotiz in `docs/lernnotizen/` schreiben, Änderungen in drei Sätzen erklären.
- Zahlen in README und Doku stammen nur aus echten Läufen. Jede Messung wird mit Datum, Modell und Befehl abgelegt.
- **Trennung von Entwicklungs- und Testfragen:** Schwellen und Prompts werden nur auf einem Entwicklungsteil eingestellt. Gemessen wird auf einem getrennten Testteil. Sonst wären die Zahlen geschönt, genau wie in v1.
- Sprachmodell: höchstens `qwen3.5:9b`. Kleinere Modelle nur, wenn eine Messung zeigt, dass sie reichen.
- Das Repository ist öffentlich. Secrets kommen nur aus der Umgebung, nie ins Repo.

## Änderung an deiner Reihenfolge (Empfehlung)

Deine Reihenfolge bleibt fast gleich. Ich empfehle zwei Änderungen:

**1. Ein kleines Paket 0 vorweg.** Strenge Typprüfung (mypy) und Logging gehören an den Anfang. Dann prüfen sie jede spätere Zeile mit. Am Ende eingebaut, müsste man den ganzen Code nachträglich reparieren.

**2. LangGraph vor die MCP-Modernisierung ziehen.** Der Grund ist ein harter Konflikt, gemessen an den Paketangaben von PyPI:

- CrewAI verlangt `mcp<2` (auch in der neuesten Version 1.15.41).
- FastMCP 4 und das neue LangChain-MCP verlangen `mcp>=2.3`.

Beides kann nicht gleichzeitig installiert sein. Bliebe die Reihenfolge, müsste ich MCP in Paket 4 auf der alten Version 1.x bauen und in Paket 6 alles noch einmal umbauen. Langfuse kommt aus demselben Grund nach LangGraph: Sonst würde ich zuerst CrewAI anbinden und das danach wegwerfen.

| Neu | Inhalt | Tag | Deine Nummer |
|---|---|---|---|
| 0 | Fundament | v1.0.3 | neu |
| 1 | Deutsch durchgängig | v1.1 | 1 |
| 2 | Echtes Embedding, bessere Suche, besserer Router | v1.2 | 2 |
| 3 | FastAPI-Backend mit Sicherheit | v1.3 | 3 |
| 4 | LangGraph statt CrewAI | v1.4 | 6 |
| 5 | MCP 2.x mit HTTP und Authentifizierung | v1.5 | 4 |
| 6 | Langfuse | v1.6 | 5 |
| 7 | Qualität und Auslieferung | v2.0 | 7 |

---

## Paket 0 – Fundament (v1.0.3)

**Ziel:** Ab hier wird jede Änderung automatisch streng geprüft.

- `mypy --strict` für `src/`, Fehler beheben, in `make quality` und CI aufnehmen
- Strukturiertes Logging (JSON) mit Request-ID; `LOG_LEVEL` wird endlich benutzt
- CI: `pip-audit` (bekannte Schwachstellen), Testabdeckung mit Mindestwert, Actions per Commit-Hash gepinnt
- Kleine Abhängigkeiten auf aktuelle Minor-Versionen heben (Ruff, Pytest, Pydantic, Gradio), Lock-Datei neu erzeugen
- README-Fehler korrigieren: 9 statt 10 Prüffunktionen, „hybride Suche“ ehrlich beschreiben
- Die beiden fast immer gültigen Kennzahlen (Werkzeugauswahl, Quellenangabe) als solche kennzeichnen. Echte Ersatzmessungen kommen in Paket 2 und 4.

**Fertig, wenn:** mypy streng grün, alle 84 Tests grün, CI grün.

## Paket 1 – Deutsch durchgängig (v1.1)

- Die 18 Richtlinien, die Regeltitel und Meldungen in `rules.json`, die Prompts und die Fehlermeldungen auf Deutsch
- Dokument-IDs, Regel-IDs und Abschnittsnummern bleiben gleich, damit Verweise stabil sind
- Wörterbuch-Notlösung `QUERY_EXPANSIONS` entfernen
- Die Suchen-und-Ersetzen-Übersetzung im MCP-Client entfernen, weil die Texte jetzt an der Quelle deutsch sind
- Spracherkennung per Wortliste entfernen: Standardsprache ist Deutsch
- **Eingabefilter neu, in Schichten:**
  1. Normalisieren: Unicode NFKC, unsichtbare Zeichen entfernen, gesperrte Schreibweise („I g n o r e“) zusammenziehen
  2. Muster für Deutsch und Englisch, nach Kategorien: Anweisung überschreiben, Rolle wechseln, Systemprompt auslesen, Shell/Code, Rechte erweitern
  3. Derselbe Filter prüft eingelesene Dokumente; ein Treffer wird geloggt statt still verworfen
- Neuer Angriffs-Testsatz mit mindestens 40 Angriffen und 40 harmlosen Fragen. Gemessen werden Erkennungsrate **und** Fehlalarme.
- Ehrliche Grenze in der Doku: Ein Musterfilter ist nur die erste Schicht. Die eigentliche Sicherheit kommt aus Rechten im Code (Paket 3) und der Trennung von Dokumenttext und Anweisung.

**Fertig, wenn:** keine englischen Texte mehr für Nutzer sichtbar, Angriffs-Testsatz gemessen, alle Tests grün.

## Paket 2 – Echtes Embedding, bessere Suche, besserer Router (v1.2)

- **Embedding über Ollama** (`/api/embed`). Kandidaten:
  - `bge-m3`: laut Vergleichen am verlässlichsten für Deutsch
  - `qwen3-embedding:0.6b`: stark und klein
  - `embeddinggemma`: bereits installiert
- Auswahl **per Messung**, nicht per Bauchgefühl. Hashing bleibt nur für schnelle Tests.
- **Persistenter Index:** FAISS-Datei plus Manifest (Modellname, Dimension, Hash der Wissensbasis). Neuaufbau per Befehl `novabank-index rebuild`. Beim Start wird geprüft, ob Index und Wissensbasis zusammenpassen.
- Der Index wird einmal geladen und nicht mehr pro MCP-Prozess neu berechnet.
- Schwellen für „keine Antwort“ werden neu bestimmt, auf dem Entwicklungsteil.
- Optional: Reranker (Cross-Encoder, z. B. `bge-reranker-v2-m3`). Er kommt nur dazu, wenn er messbar hilft.
- **Router:** Regeln für die Fall-ID bleiben. Die Erkennung der Absicht wird semantisch: Beispielsätze je Absicht, Vergleich per Embedding, kein Sprachmodell nötig, schnell und nachvollziehbar.
- **Evaluation:**
  - mindestens 30 Suchfragen: Umformulierungen, Fragen ohne Antwort, Teilenummern und Abschnittsnummern (z. B. „Was steht in NB-DOC-001 Abschnitt 3.1?“)
  - mindestens 40 Routing-Fälle
  - Kennzahlen: Recall@5, MRR, nDCG@5, Ablehnungsgenauigkeit, Latenz
  - getrennter Entwicklungs- und Testteil
- **Vorher-nachher-Tabelle** Hashing gegen echtes Modell in der README

**Fertig, wenn:** Modellwahl mit Messung begründet, Vergleichstabelle aus echtem Lauf in der README.

## Paket 3 – FastAPI-Backend mit Sicherheit (v1.3)

- **Endpunkte:** `POST /v1/auth/token`, `POST /v1/chat`, `GET /v1/cases/{id}`, `POST /v1/search`, `GET /health`, `GET /ready`, mit Pydantic-Schemas und OpenAPI-Doku
- **Anmeldung:** JWT mit kurzer Laufzeit, Schlüssel nur aus der Umgebung, Passwörter mit Argon2. Demo-Nutzer kommen aus einer Seed-Datei, die nur Hashes enthält.
- **Rollen:** Sachbearbeiter, Prüfer, Admin
- **Rechte auf Dokument- und Fallebene:**
  - Jedes Dokument bekommt eine Schutzklasse, jeder Fall eine Zuständigkeit.
  - Die Suche filtert **vor** dem Ranking. FAISS und BM25 sehen nur erlaubte Dokumente, damit auch Rangplatz und „keine Antwort“ nichts verraten.
  - Die Prüfung sitzt im Code und in den MCP-Werkzeugen, nie im Prompt.
- **Entscheidungslogik in einen Fachservice:** Die Empfehlung (Genehmigungskandidat / manuelle Prüfung / Ablehnung) wandert aus dem MCP-Client in einen eigenen Service. Welche Regeln hart sind, steht nur noch im Regelwerk.
- **Schutz:** Rate Limiting, restriktives CORS, Sicherheitsheader, Audit-Log als JSON-Lines mit Hash-Kette (Manipulation wird erkennbar)
- **Gradio wird Client der API** und ruft den Ablauf nicht mehr direkt im Prozess auf
- **Sicherheitstests:** Ein Nutzer ohne Recht bekommt ein Dokument weder über die Suche noch über einen `document_id`-Filter, die Fall-ID, Fehlermeldungen oder Unterschiede in Rangfolge und Antwortzeit.
- Neue Abhängigkeiten (klein, Standard): `fastapi` (ist schon transitiv da), `uvicorn`, `pyjwt`, `argon2-cffi`, `slowapi`

**Fertig, wenn:** alle Sicherheitstests grün, OpenAPI-Doku erreichbar, UI läuft über die API.

## Paket 4 – LangGraph statt CrewAI (v1.4)

- **CrewAI entfernen.** Das ist eine große Abhängigkeit, die verschwindet. Du hast den Tausch vorgegeben, ich bestätige ihn mit dieser Freigabe noch einmal.
- **Graph:**
  - Router-Knoten
  - Werkzeug-Knoten über MCP (vorerst noch MCP 1.x mit `langchain-mcp-adapters`)
  - Antwort-Knoten mit `qwen3.5:9b` über `langchain-ollama`
  - Prüf-Knoten
- **Checkpointer** (SQLite): Der Zustand jeder Anfrage bleibt gespeichert.
- **Pause für menschliche Freigabe** (`interrupt`) vor der Entscheidungsvorlage. Fortsetzung über die API mit Freigabe oder Ablehnung, beides im Audit-Log.
- Der verifizierte MCP-Rückfallweg bleibt erhalten.
- **Das 24B-Profil entfällt** (über deiner Hardware-Grenze). Die vollständige Prüfung läuft mit `qwen3.5:9b` und wird gemessen.
- **Antwortqualität messen:**
  - Zahlen-Treue: Jede Zahl in der Antwort muss exakt in der Werkzeug-Ausgabe vorkommen. Das ist deterministisch prüfbar.
  - Quellen-Korrektheit: Zitierte Dokument-IDs müssen unter den gefundenen sein, Abschnitte müssen stimmen.
  - Faithfulness: Aussagen müssen durch die Belege gestützt sein. Das bewertet ein lokales Modell als Richter. Weil ein 9B-Richter schwach ist, wird er an einer kleinen, von Hand bewerteten Stichprobe geprüft und die Übereinstimmung ehrlich angegeben.

**Fertig, wenn:** CrewAI ist nicht mehr installiert, die Freigabe-Pause funktioniert über die API, Qualitätszahlen aus echtem Lauf dokumentiert.

## Paket 5 – MCP 2.x mit HTTP und Authentifizierung (v1.5)

- **Zuerst ein kurzer Prüf-Spike:** Passen FastMCP 4, `langchain[mcp]` und LangGraph 1.2 zusammen? Ergebnis kommt vorher zu dir.
- **Server** auf FastMCP 4 (verlangt `mcp>=2.3`). FastMCP bleibt die einzige Schnittstelle zur Fachlogik.
- **Transport Streamable HTTP** (zustandslos nach Spezifikation 2026-07-28), stdio bleibt für lokale Entwicklung
- **Authentifizierung:** Der MCP-Server prüft das JWT der API (Rolle: Resource Server). Der Nutzerkontext wird bis in jedes Werkzeug durchgereicht, und die Rechteprüfung aus Paket 3 greift dort.
- Ehrliche Grenze: kein eigener vollständiger OAuth-2.1-Autorisierungsserver
- Tests: Werkzeugaufruf ohne Token, mit abgelaufenem Token und mit fremder Rolle wird abgelehnt.

## Paket 6 – Langfuse (v1.6)

- Jede Anfrage wird aufgezeichnet: Prompt, Antwort, Tool-Aufrufe, Dauer, Token, Kosten
- Kosten: Lokale Modelle haben keine API-Kosten. Gezeigt wird ein einstellbarer Preis pro Token, damit der Mechanismus sichtbar ist. Das steht so auch in der Doku.
- Testfragen aus Paket 2 und 4 als Datensatz in Langfuse, Auswertungsläufe als Experimente
- Self-Hosting per Docker Compose als optionales Profil. Das Python-SDK v5 braucht Langfuse-Server ab Version 4.59.
- In Tests abgeschaltet: ohne Schlüssel kein Netzwerkzugriff

## Paket 7 – Qualität und Auslieferung (v2.0)

- Testpyramide vervollständigen: Unit, Integration, End-to-End, Sicherheit
- Tests mit echtem Sprachmodell bekommen eine eigene Markierung. Sie laufen lokal bzw. auf Knopfdruck, weil GitHub-Runner kein 9B-Modell sinnvoll ausführen. Das steht offen in der Doku.
- Docker Compose: API, UI, optional Langfuse. Ollama läuft auf dem Mac nativ, wegen der GPU.
- README auf Deutsch, neues Architekturdiagramm, Grenzen ehrlich benannt
- Die Office- und PDF-Dateien in `output/` neu erstellen oder als v1-Archiv kennzeichnen. Das entscheide ich mit dir, wenn wir dort sind.

---

## Entscheidungen, die ich von dir brauche

1. **Reihenfolge:** Paket 0 vorweg, LangGraph vor MCP-HTTP, Langfuse danach? *(Empfehlung: ja)*
2. **Modelle herunterladen:** Für den Vergleich in Paket 2 `ollama pull bge-m3` (etwa 1,2 GB) und `ollama pull qwen3-embedding:0.6b` (etwa 0,6 GB). Den optionalen Reranker frage ich erst, wenn es so weit ist. *(Empfehlung: ja)*
3. **24B-Profil streichen:** Alles läuft mit `qwen3.5:9b`. *(Empfehlung: ja)*
4. **CrewAI entfernen** in Paket 4, wie von dir vorgegeben. *(Empfehlung: ja)*

## Abweichungen bei der Umsetzung

| Paket | Geplant | Umgesetzt | Grund |
|---|---|---|---|
| 4 | Werkzeug-Knoten mit `langchain-mcp-adapters` | eigener kleiner MCP-Client | Der Adapter macht MCP-Werkzeuge zu Werkzeugen, die das Modell selbst wählt. Das widerspricht „Least Agency“. Außerdem verlangt er `mcp<2`. |
| 5 | Server auf FastMCP 4 | offizielles MCP-SDK 2.3 (`MCPServer`) | Das SDK bringt Streamable HTTP und Token-Prüfung schon mit. FastMCP 4 hätte rund 20 zusätzliche Pakete gebracht (u. a. `cyclopts`, `websockets`, `watchfiles`, `pyperclip`), die das Projekt nicht braucht. |
| 5 | MCP-Server prüft das JWT der API | eigenes MCP-Token (Audience `novabank-mcp`, 5 Minuten) | Die MCP-Spezifikation verbietet „Token Passthrough“: Ein Server darf nur Tokens annehmen, die für ihn ausgestellt wurden. |
