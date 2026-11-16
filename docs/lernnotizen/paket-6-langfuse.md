# Lernnotiz Paket 6 – Langfuse: jeden Lauf nachvollziehen (v1.6)

## Worum ging es?

Bis v1.5 gab es Logs und das technische Protokoll in der Antwort. Damit sieht man, **dass** etwas passiert ist, aber nicht bequem, **was** das Modell bekommen und geantwortet hat, wie lange jeder Schritt dauerte und wie viele Token verbraucht wurden. Für ein LLM-System braucht man dafür ein Werkzeug für „LLM Observability“. Langfuse ist Open Source und lässt sich selbst betreiben. Bei einer Bank ist das wichtig, weil Prompts Kundendaten enthalten können.

## Was wurde gebaut?

### 1. Tracing, standardmäßig aus

`observability/tracing.py` schaltet Langfuse nur ein, wenn `LANGFUSE_ENABLED=true` **und** beide Projektschlüssel gesetzt sind. Sonst wird kein Client erzeugt und nichts verlässt den Rechner. Die Tests laufen deshalb ohne Netzwerk.

Wenn es an ist, wird jeder Lauf ein **Trace**:

- jeder Graph-Knoten (`route`, `collect_evidence`, `generate`, `verify`, …) als Span mit Ein- und Ausgabe,
- der Modellaufruf als **Generation** mit Prompt, Antwort, Dauer und Token,
- die Person als **pseudonyme Nutzer-ID**, der Thread als **Sitzung**. So hängen Entwurf und spätere Freigabe einer Entscheidungsvorlage zusammen.

Technisch hängt sich der `CallbackHandler` von Langfuse an LangGraph und LangChain an. Den Code der Knoten musste ich dafür nicht ändern.

### 2. Datenschutz

- **Pseudonym statt Name im Nutzerfeld:** Die Nutzer-ID ist ein HMAC des Benutzernamens. Der Schlüssel ist das JWT-Secret der Anwendung, das der Langfuse-Server nie sieht. So kann der Server die IDs nicht durch Ausprobieren bekannter Namen zurückrechnen. **Aber:** Beim Ansehen eines echten Traces habe ich gemerkt, dass Namen trotzdem im Inhalt stehen: im Graph-Zustand (`requested_by`) und im Freigabevermerk der Entscheidungsvorlage, der die freigebende Person bewusst nennt. Das Pseudonym hält Namen also aus Filtern und Dashboards heraus, nicht aus dem Inhalt. Deshalb muss der Zugang zu Langfuse so streng sein wie der Zugang zu den Fallakten. Das steht so in der Sicherheitsdoku.
- **Kein Token im Trace:** Das Token ist Laufzeit-Kontext, nicht Zustand. Zusätzlich entfernt eine Maskierfunktion alles, was wie ein JWT aussieht. Ein Test fängt einen echten Trace im Speicher ab und sucht das Token darin.
- **Keine Langfuse-Schlüssel im MCP-Prozess:** Die Positivliste für den MCP-Unterprozess schließt die Langfuse-Schlüssel ausdrücklich aus.

### 3. Selbst betreiben mit Docker Compose

`deploy/langfuse/docker-compose.yml` baut auf der offiziellen Datei auf, ist aber für eine lokale Demo verschlankt und abgesichert:

- ohne KI-Gateway, Telemetrie an Langfuse aus,
- alle Ports nur auf `127.0.0.1`, die Datenbanken gar nicht nach außen,
- **keine Standardpasswörter**: `scripts/langfuse_env.py` erzeugt zufällige Geheimnisse in eine Datei, die Git ignoriert und nur der Besitzer lesen darf,
- Organisation, Projekt, Schlüssel und Admin werden beim Start automatisch angelegt.

Das SDK v5 braucht einen Server ab 4.59; das Image ist auf 4.80.0 festgelegt.

### 4. Kosten

Lokale Modelle haben keine API-Kosten. Damit der Mechanismus trotzdem sichtbar ist, legt `novabank-langfuse setup` eine Modelldefinition mit einem **einstellbaren Preis** an. Langfuse rechnet dann aus den Token die Kosten aus. Der Standardpreis ist 0. Für die Demo habe ich einen ausgedachten Preis eingetragen; das ist eine Annahme und kein echter Preis.

### 5. Datensätze und Experimente

- `novabank-langfuse datasets` lädt die 17 Antwortfragen und den Test-Split der Suchfragen als Datensätze hoch. Die IDs sind fest, ein zweites Hochladen aktualisiert statt zu verdoppeln.
- `novabank-langfuse experiment` schickt jede Frage durch den echten Ablauf. Jede Antwort wird ein Trace, dazu kommen Bewertungen (Fakten richtig, Ausführungsmodus). Zwei Läufe kann man in Langfuse nebeneinander vergleichen, zum Beispiel vor und nach einer Prompt-Änderung.

## Was ich beim Bauen gefunden habe

- **Port 3000 war belegt.** Auf dem Rechner lief schon ein anderer Container auf Port 3000. Den habe ich nicht angefasst. Der Port ist jetzt einstellbar (`LANGFUSE_PORT`).
- **Das erste Experiment ist komplett gescheitert:** „asyncio.run() cannot be called from a running event loop“. Der Experiment-Runner von Langfuse läuft selbst in einer Event-Loop, und der MCP-Client startet eine eigene. Lösung: Die Aufgabe läuft in einem eigenen Thread (`asyncio.to_thread`). Der Trace-Kontext wird dabei mitkopiert.
- **`setup` hätte Definitionen gestapelt.** Jeder Aufruf legte eine neue Modelldefinition an. Jetzt ersetzt der Befehl seine eigene frühere Definition.
- **Tests ohne Server:** Das SDK nimmt einen eigenen `span_exporter` an. Damit kann ich einen echten Trace im Speicher abfangen und prüfen, ganz ohne Netzwerk.

## Live-Prüfung

Am 16.11.2026 auf dem M4 Pro, Langfuse 4.80.0 lokal per Docker Compose, echtes Modell:

- `novabank-langfuse check`, `setup` und `datasets` gegen den echten Server: verbunden, eine Modelldefinition, Datensätze mit 17 und 24 Einträgen.
- Experiment mit 17 Fragen: Durchschnitt `facts_correct` 0,882 (15 von 17, passt zu Lauf 3 aus Paket 4).
- Über die Langfuse-API geprüft: 14 Generationen mit Token (12.124 Eingabe, 2.192 Ausgabe). Mit dem angenommenen Preis von 0,10 / 0,40 USD pro 1 Mio. Token ergibt das 0,002089 USD. Die Rechnung stimmt mit den Token überein. Median der Modellaufrufe 4,4 s.
- Alle Chat-Traces tragen dieselbe pseudonyme Nutzer-ID, jede hat eine eigene Sitzung. In keinem der gespeicherten Einträge steht ein JWT.

Das sind Einzelwerte aus einem Lauf, keine Messreihe.

## Welche Alternativen gab es?

| Entscheidung | Gewählt | Alternative | Warum so |
|---|---|---|---|
| Werkzeug | Langfuse, selbst gehostet | LangSmith, Arize Phoenix, nur OpenTelemetry + Jaeger | Open Source, selbst betreibbar, Datensätze und Experimente eingebaut. LangSmith ist primär ein Cloud-Dienst. |
| Anbindung | LangChain-Callback | jeden Knoten mit `@observe` markieren | Der Callback sieht alle Knoten und den Modellaufruf ohne Änderungen im Graphen. |
| Nutzer-ID | HMAC-Pseudonym | Klarname | Datensparsamkeit; für Fehlersuche reicht eine stabile ID. |
| Kosten | Modelldefinition in Langfuse | Kosten im eigenen Code rechnen | So rechnet Langfuse auch alte Traces neu, wenn sich der Preis ändert. |
| Standard | aus | an | Kein Netzwerkverkehr ohne bewusste Entscheidung. |

## Fragen im Vorstellungsgespräch

**„Was ist der Unterschied zwischen Logging und Tracing?“**
Ein Log ist eine einzelne Zeile zu einem Zeitpunkt. Ein Trace verbindet alle Schritte einer Anfrage zu einem Baum: welcher Schritt wie lange dauerte, was hineinging und was herauskam. Bei einem LLM-Ablauf sieht man so genau, welchen Prompt das Modell bekommen hat.

**„Ist es nicht gefährlich, Prompts zu speichern?“**
Doch, wenn echte Kundendaten darin stehen. Deshalb: selbst gehostet im eigenen Netz, standardmäßig aus, Nutzer pseudonymisiert, Tokens maskiert. Für echte Daten käme noch eine Maskierung personenbezogener Daten und eine Löschfrist dazu. Das steht als Grenze in der Doku.

**„Wofür braucht man Datensätze und Experimente?“**
Um Änderungen zu vergleichen. Wenn ich den Prompt ändere, schicke ich dieselben 17 Fragen noch einmal durch und sehe in Langfuse nebeneinander, ob die Fakten besser oder schlechter geworden sind.

**„Warum zeigt ihr Kosten, wenn das Modell lokal läuft?“**
Damit der Mechanismus sichtbar ist, und für den Vergleich: Mit dem Preis eines Cloud-Modells sieht man, was dieselbe Last dort kosten würde. Der Preis ist in der Doku ausdrücklich als Annahme markiert.
