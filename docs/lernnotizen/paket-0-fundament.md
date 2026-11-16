# Lernnotiz Paket 0 – Fundament (v1.0.3)

## Worum ging es?

Bevor wir neue Funktionen bauen, sollte das Werkzeug stimmen. Paket 0 sorgt dafür, dass ab jetzt jede Änderung automatisch streng geprüft wird. Neue Fachfunktionen gibt es in diesem Paket nicht.

## Was wurde gebaut?

### 1. Strenge Typprüfung mit mypy

**Was ist das?** Python prüft Typen normalerweise erst, wenn das Programm läuft. mypy liest den Code vorher und findet Fehler wie „hier kommt vielleicht `None` an, aber du rufst `.model` darauf auf“.

**Was genau?** `mypy --strict` für `src`, `scripts` und `tests`, dazu das Pydantic-Plugin. Am Anfang gab es 46 Fehler in `src`. Jetzt sind es 0.

**Ein Beispiel für einen echten Fund:** `build_dataset()` gab die Referenzlabels als `dict[str, object]` zurück. Damit wusste niemand, was darin steht. Jetzt ist es ein `TypedDict` namens `GroundTruth` mit festen Feldern.

**Warum für Tests lockerer?** In Tests wird der Code im Funktionskörper geprüft. Die Testfunktionen selbst müssen aber keine Typangaben haben. Das ist in vielen Projekten üblich, weil pytest die Argumente ohnehin per Name einsetzt.

**`py.typed`:** Eine leere Datei, die sagt: „Dieses Paket ist typisiert.“ Ohne sie behandelt mypy unser eigenes Paket wie eine fremde Bibliothek ohne Typen.

### 2. Strukturiertes Logging

**Was ist das?** Jede Logzeile ist ein JSON-Objekt, zum Beispiel:

```json
{"timestamp": "...", "level": "INFO", "logger": "...mcp.server",
 "message": "mcp_tool_completed", "tool": "check_compliance", "duration_ms": 3.1}
```

Maschinen können das durchsuchen und auswerten, etwa in Grafana Loki oder Elasticsearch.

**Request-ID:** Jede Anfrage in der UI bekommt eine eigene ID. Alle Logzeilen dieser Anfrage tragen dieselbe ID. So findet man im Fehlerfall alles, was zu einer Anfrage gehört. Technisch läuft das über `contextvars`: Die ID gilt automatisch für den aktuellen Ablauf, ohne dass man sie durch jede Funktion reichen muss.

**Zwei wichtige Regeln:**

1. **Logs gehen nach stderr, nie nach stdout.** Der MCP-Server spricht über stdout mit dem Client. Eine Logzeile auf stdout würde das Protokoll zerstören.
2. **Die Anfrage selbst wird nie geloggt.** Geloggt werden nur Länge, Absicht, Dauer und Ergebnis. Sonst würden Kundendaten im Log landen. Das widerspricht dem Datenschutz (DSGVO, Datensparsamkeit). Ein Test prüft das ausdrücklich.

**Bibliothek bleibt still:** Ein `NullHandler` sorgt dafür, dass das Paket nichts ausgibt, solange ein Einstiegspunkt (UI, MCP-Server) das Logging nicht einschaltet. Das ist die offizielle Empfehlung für Python-Bibliotheken.

### 3. Sicherheitslücken in den Abhängigkeiten behoben

**Der Fund:** `pip-audit` hat in der Lock-Datei von v1.0.2 **104 bekannte Sicherheitslücken in 14 Paketen** gefunden. Die meisten kamen indirekt über CrewAI, Gradio oder torch herein.

**Die Lösung:** Gezielte Updates. Danach bleiben nur 5 Meldungen zu `chromadb` übrig. Dafür gibt es noch keine reparierte Version, und chromadb kommt nur über CrewAI herein. Die Ausnahme ist in `make deps-audit` begründet und fällt in Paket 4 weg.

**Die Lehre:** Eine Lock-Datei macht Installationen reproduzierbar. Sie hält aber auch alte, verwundbare Versionen fest. Deshalb braucht man beides: Lock-Datei **und** regelmäßigen Schwachstellen-Scan.

### 4. CI gehärtet

- **Actions per Commit-Hash gepinnt.** `actions/checkout@v5` ist nur ein Name. Der Besitzer kann ihn jederzeit auf anderen Code zeigen lassen. Ein Hash wie `@3d3c42e…` kann nicht nachträglich geändert werden. Dependabot schlägt Updates vor.
- **`persist-credentials: false`.** Der GitHub-Token bleibt nicht im Arbeitsverzeichnis liegen, wo ihn späterer Code lesen könnte.
- **Testabdeckung mit Untergrenze.** Gemessen sind 84,5 %, die Grenze liegt bei 80 %.
- **Neuer Job `dependency-audit`.** Er läuft bei jedem Pull Request.

### 5. Ehrlichere Dokumentation

- README: 9 statt 10 Prüffunktionen, und es steht offen da, dass die Standard-Suche keine Bedeutungssuche ist.
- Evaluationsbericht: Ein neues Feld `metric_notes` kennzeichnet zwei Kennzahlen, die fast immer 1,0 sind.

## Welche Alternativen gab es?

| Entscheidung | Gewählt | Alternative | Warum so |
|---|---|---|---|
| Typprüfer | mypy | pyright, ty | mypy ist der verbreitetste Standard und hat ein offizielles Pydantic-Plugin. pyright ist schneller und ebenfalls gut. |
| Logging | Standardbibliothek mit eigenem JSON-Formatter | structlog, loguru | Keine neue Abhängigkeit. structlog wäre bequemer, bringt aber eine weitere Bibliothek ins Projekt. Für unseren Umfang reicht die Standardbibliothek. |
| Schwachstellen-Scan | pip-audit | Safety, Trivy, Snyk | pip-audit ist frei, offiziell von der Python Packaging Authority und nutzt die öffentliche OSV-Datenbank. |
| Lock-Datei erzeugen | uv | pip-tools, Poetry | uv ist sehr schnell und übernimmt bestehende Versionen, wenn man das will. So bleibt der Unterschied klein. |
| Ausnahme für chromadb | befristet ignorieren | CrewAI sofort entfernen | Das Entfernen ist Paket 4. Hier vorzugreifen hätte Paket 0 stark vergrößert. |

## Was bewusst noch nicht gelöst ist

- Pydantic bleibt unter 2.13, weil CrewAI das verlangt. Das Update kommt nach Paket 4.
- Die 5 chromadb-Meldungen bleiben bis Paket 4 offen.
- Code, der in einem Unterprozess läuft (MCP-Server über stdio), zählt die Abdeckungsmessung nicht mit.

## Fragen im Vorstellungsgespräch

**„Warum strenges mypy und nicht einfach Tests?“**
Tests prüfen Beispiele, mypy prüft alle Wege durch den Code. Viele Fehler, etwa ein vergessener `None`-Fall, findet ein Typprüfer sofort, ein Test nur, wenn jemand genau diesen Fall geschrieben hat. Beides ergänzt sich.

**„Warum loggt ihr den Prompt nicht? Für die Fehlersuche wäre das doch praktisch.“**
Weil im Prompt personenbezogene Daten stehen können. Logs werden oft lange aufbewahrt und von vielen Leuten gelesen. Für die Fehlersuche reichen Request-ID, Absicht, Dauer und Fehlertyp. Wer die Inhalte wirklich braucht, bekommt sie über ein eigenes, zugriffsgeschütztes Tracing wie Langfuse (Paket 6), mit Löschfristen.

**„Ihr habt eine Lock-Datei. Warum trotzdem 104 Sicherheitslücken?“**
Weil die Lock-Datei Versionen einfriert. Das ist gewollt, damit jede Installation gleich ist. Neue Lücken werden aber laufend bekannt. Deshalb läuft jetzt bei jedem PR ein Scan, und Updates passieren bewusst und geprüft.

**„Warum ignoriert ihr chromadb? Ist das nicht gefährlich?“**
Für die Meldungen gibt es keine reparierte Version, Updaten geht also nicht. chromadb kommt nur über CrewAI herein, unser Code benutzt es nicht, und CrewAI arbeitet bei uns ohne Memory. Die Ausnahme ist mit Begründung und Ablaufdatum dokumentiert: Sie fällt mit CrewAI weg. Eine unbegründete Ausnahme wäre gefährlich, eine dokumentierte und befristete ist ein normales Risikomanagement.

**„Warum nach stderr loggen?“**
Beim MCP-Transport über stdio ist stdout der Datenkanal zwischen Client und Server. Jede fremde Zeile dort macht das Protokoll kaputt. stderr ist für Diagnose da.

**„Was bringt die Request-ID?“**
In einem System mit vielen gleichzeitigen Anfragen mischen sich die Logzeilen. Mit der ID kann man alle Zeilen einer Anfrage herausfiltern. In einem verteilten System gibt man die ID zusätzlich an andere Dienste weiter, das ist die Grundidee von Distributed Tracing.

**„Warum Actions per Hash pinnen?“**
Ein Tag kann umgehängt werden. Wird ein Action-Repository übernommen, kann ein Angreifer den Tag auf Schadcode zeigen lassen, und alle Projekte mit diesem Tag führen ihn aus. So etwas ist in der Praxis schon passiert. Ein Commit-Hash ist unveränderlich.
