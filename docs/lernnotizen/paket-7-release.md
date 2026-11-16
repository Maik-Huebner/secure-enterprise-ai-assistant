# Lernnotiz Paket 7 – Qualität und Auslieferung (v2.0)

## Worum ging es?

Nach den Paketen 0 bis 6 war die Technik fertig. Paket 7 macht daraus ein Projekt, das jemand
anderes starten, prüfen und verstehen kann: eine vollständige Testpyramide, Container für API
und Oberfläche, eine deutsche README mit allen gemessenen Zahlen und ehrlichen Grenzen.

## Was wurde gebaut?

### 1. Testpyramide mit Live-Ebene

| Ebene | Tests | Was sie prüfen |
|---|---:|---|
| Unit | 238 | Rechner, Regeln, Suche, Router, Graph mit Testmodellen, Antwortprüfung, Tracing |
| Integration | 5 | MCP-Server registriert genau die vier Werkzeuge |
| End-to-End | 5 | echter MCP-Unterprozess, Entscheidungsvorlage, API-Abläufe |
| Sicherheit | 58 | Anmeldung, Rollen, Umwege, Tokens, MCP über HTTP, Audit |
| **Live** | 4 | echtes Modell und echte Embeddings über Ollama |

Die Live-Tests haben die Markierung `live` und laufen nur mit `make test-live`. GitHub-Runner
können ein 9B-Modell nicht sinnvoll ausführen. Die Live-Tests prüfen Verhalten, nicht Wortlaut:
richtige Fakten, Zahlen aus dem Werkzeug, „keine Antwort“ ohne Modellaufruf, fremder Fall bleibt
verborgen.

### 2. Docker Compose

`compose.yaml` startet API und Oberfläche aus **einem** Image mit drei Einstiegspunkten
(`novabank-api`, `novabank-ui`, `novabank-mcp`). Ollama läuft nativ auf dem Mac, weil Docker auf
macOS keinen Zugriff auf die GPU hat.

Absicherung der Container:

- Ports nur auf `127.0.0.1`,
- schreibgeschütztes Dateisystem, nur `/tmp` und das Daten-Volume sind beschreibbar,
- keine Linux-Capabilities, `no-new-privileges`,
- nur ausdrücklich genannte Variablen gelangen in die Container, nicht die ganze `.env`,
- der MCP-Server (Profil `mcp-http`) ist nur im internen Netz erreichbar.

Für Benutzer im Container gibt es jetzt `novabank-users add … --password-stdin`. Das Passwort
kommt so nie als Argument in die Prozessliste oder den Shell-Verlauf.

### 3. Deutsche README

Die README ist jetzt deutsch, mit allen Messwerten aus den echten Läufen, neuen Screenshots der
Oberfläche (Anmeldung, geprüfte Antwort, Freigabe durch eine zweite Person) und einem Abschnitt
„Grenzen (ehrlich)“.

## Was ich beim Bauen gefunden habe

- **Ein echter Fehler aus Paket 5:** Mit MCP 2.x verpackt der stdio-Transport Fehler in eine
  `ExceptionGroup`. Fragte die Sachbearbeitung einen fremden Fall an, hätte die API **500**
  statt **404** geliefert. Die Unit-Tests haben das nicht gesehen, weil sie einen Sammler ohne
  Unterprozess benutzen. Gefunden haben es die neuen Live-Tests. Die Korrektur steht auf dem
  Zweig von Paket 5 und wurde in 6 und 7 übernommen; ein End-to-End-Test mit echtem Unterprozess
  sichert sie ab.
- **Markdown-Absätze in der Entscheidungsvorlage:** Der Satz „Die Zahlen stammen unverändert …“
  hing am letzten Listenpunkt, weil die Leerzeile fehlte. Beim Ansehen des Screenshots aufgefallen.
- **Port 3000 war belegt** (siehe Paket 6) – Ports sind jetzt überall einstellbar.
- **CI-Prüfung der Compose-Dateien:** Die CI prüft, dass `compose.yaml` gültig ist und dass der
  Langfuse-Stack ohne erzeugte Geheimnisse **nicht** startet.

## Live-Prüfung im Container (16.11.2026, M4 Pro)

- Wissensfrage über die API: 5,1 s, `llm_grounded`.
- Sachbearbeitung Team Nord fragt Fall 31 an: 404 „Unbekannte synthetische Fall-ID“.
- Entscheidungsvorlage: 1,0 s, Status `awaiting_approval`; in der Oberfläche gibt eine zweite
  prüfende Person frei.

Einzelwerte, keine Messreihe.

## Welche Alternativen gab es?

| Entscheidung | Gewählt | Alternative | Warum so |
|---|---|---|---|
| Ollama | nativ auf dem Host | Ollama-Container | Auf dem Mac nutzt nur das native Ollama die GPU. Unter Linux mit NVIDIA wäre ein Container möglich. |
| Images | ein Image, drei Befehle | je ein Image pro Dienst | Gleicher Code, gleiche Abhängigkeiten, einmal bauen. |
| Live-Tests | lokal per Markierung | in der CI mit kleinem Modell | Ein anderes Modell würde etwas anderes testen als das, was ausgeliefert wird. |
| Container-Rechte | read-only, ohne Capabilities | Standard | Kostet nichts und verkleinert die Angriffsfläche. |

## Fragen im Vorstellungsgespräch

**„Wie testet man ein System mit LLM?“**
In Schichten. Alles Deterministische (Rechner, Regeln, Suche, Rechte) testet man normal. Den
Ablauf testet man mit Testmodellen, die bewusst richtig oder falsch antworten. Das echte Modell
prüft man getrennt: mit Live-Tests auf Verhalten und mit einer Messung der Antwortqualität, bei
der ein Mensch die Antworten nachliest.

**„Warum hat der Unit-Test den 500er nicht gefunden?“**
Weil er den Transport ersetzt hat. Genau dafür gibt es End-to-End- und Live-Tests: Sie laufen
durch die echten Schichten. Seitdem gibt es einen Test, der den Fehlerweg über einen echten
MCP-Unterprozess prüft.

**„Was würdest du als Nächstes tun?“**
Einen Reranker für die Suche, eine größere Antwortsuite, die jemand anderes schreibt und prüft,
einen echten Identitätsdienst statt des gemeinsamen Schlüssels und eine Maskierung
personenbezogener Daten im Tracing.
