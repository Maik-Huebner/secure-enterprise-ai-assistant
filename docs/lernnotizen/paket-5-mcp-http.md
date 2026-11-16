# Lernnotiz Paket 5 – MCP 2.x mit HTTP und eigener Token-Prüfung (v1.5)

## Worum ging es?

Bis v1.4 lief der MCP-Server nur über **stdio**: Für jede Anfrage startet die Anwendung einen Unterprozess und spricht mit ihm über Standard-Ein- und -Ausgabe. Das ist einfach und lokal sicher. Ein anderes System, zum Beispiel ein Java-Dienst der Agentur oder ein zweiter Agent, kann so aber nicht auf die Werkzeuge zugreifen. Außerdem lief das Projekt noch auf MCP-SDK 1.x, weil CrewAI `mcp<2` verlangt hat. Mit Paket 4 ist CrewAI weg, also war der Weg frei.

## Was wurde gebaut?

### 1. Umstieg auf das offizielle MCP-SDK 2.3

In Version 2 heißt die frühere Klasse `FastMCP` jetzt `MCPServer`. Ansonsten bleiben die vier Werkzeuge gleich. Zwei Änderungen waren spürbar:

- Ergebnisfelder heißen jetzt `structured_content` und `is_error` statt `structuredContent` und `isError`.
- **Fehlertexte werden versteckt.** Wirft ein Werkzeug eine beliebige Ausnahme, sieht der Client nur „Error executing tool …“. Nur ein bewusstes `ToolError` gibt seinen Text weiter. Ich wandle deshalb genau die erwarteten Fehler (unbekannter oder fremder Fall, fehlende Rechte, ungültige Eingabe) in `ToolError` um. Alles andere bleibt verborgen, so dass keine Pfade oder internen Details nach außen gelangen. Ein Test prüft das mit einem absichtlich kaputten Werkzeug.

### 2. Streamable HTTP, zustandslos

`novabank-mcp --transport http` startet den Server als eigenen Dienst unter `http://127.0.0.1:8001/mcp`. „Zustandslos“ heißt: Jede Anfrage steht für sich, es gibt keine Sitzung auf dem Server. Das passt zur Spezifikation 2026-07-28 und lässt sich später leicht hinter einem Load Balancer mehrfach betreiben. stdio bleibt der Standard für die lokale Entwicklung (`MCP_TRANSPORT=stdio|http`).

### 3. Der MCP-Server ist ein „Resource Server“

Im Sprachgebrauch von OAuth 2.1 gibt es den **Authorization Server**, der Tokens ausstellt, und den **Resource Server**, der sie prüft. Hier stellt die API die Tokens aus, der MCP-Server prüft sie:

- Ohne Token, mit gefälschtem, abgelaufenem oder falsch adressiertem Token antwortet der Server mit **401** und dem Header `WWW-Authenticate`.
- Unter `/.well-known/oauth-protected-resource/mcp` steht, welcher Dienst die Tokens ausstellt (RFC 9728). Ein Client kann so selbst herausfinden, wo er ein Token bekommt.
- Aus dem geprüften Token wird die Person (Name, Rolle, Team). Jedes Werkzeug prüft damit die Rechte aus Paket 3.

### 4. Kein „Token Passthrough“

Das war die wichtigste Entscheidung. Die einfache Lösung wäre gewesen, das Token der API einfach an den MCP-Server weiterzureichen. Die MCP-Spezifikation verbietet genau das: Ein Server darf nur Tokens annehmen, die **für ihn** ausgestellt wurden.

Deshalb stellt die API für jeden Lauf ein **eigenes MCP-Token** aus: Audience `novabank-mcp`, gültig 5 Minuten. Folge:

- Ein API-Token öffnet den MCP-Server nicht (getestet).
- Ein MCP-Token öffnet die API nicht (getestet).
- Wird ein Token aus der Werkzeugschicht gestohlen, ist es kurz gültig und nur dort nutzbar.

### 5. Ein Werkzeugplan, zwei Wege

Der Client führt den Werkzeugplan des Routers in einer Funktion aus (`run_tool_plan`). Darunter liegt entweder stdio oder HTTP. Ein Test vergleicht die Nachweise über HTTP mit den Nachweisen ohne Netzwerk: Sie sind identisch.

## Was ich beim Bauen gefunden habe

- **Der Client hat einen 401 als „Server nicht erreichbar“ gemeldet.** Das SDK verpackt den HTTP-Status in einen allgemeinen Protokollfehler. Lösung: Der HTTP-Client merkt sich die Statuscodes und meldet bei 401/403 „fehlende Berechtigung“.
- **Das SDK warnt, wenn die Ressource des Tokens nicht geprüft wird.** Unser Prüfer kontrolliert die Audience selbst, das steht jetzt ausdrücklich in der Konfiguration (`validate_token_resource: False`, mit Kommentar).
- **Ein alter Warnfilter konnte weg.** Starlette wollte für den TestClient `httpx2`. Das kommt jetzt mit MCP 2.x mit, der Filter ist entfernt.

## Live-Prüfung (16.11.2026, M4 Pro)

MCP-Server über HTTP gestartet, Ablauf mit `MCP_TRANSPORT=http` und echtem Modell: Wissensfrage 9,6 s und Finanzfrage 10,0 s, beide `llm_grounded`. Sachbearbeiter aus Team Nord fragt Fall 31 (Team Süd) an: „nicht gefunden“. Ohne Token liefert der Server 401. Einzelwerte, keine Messung.

## Welche Alternativen gab es?

| Entscheidung | Gewählt | Alternative | Warum so |
|---|---|---|---|
| Server-Bibliothek | offizielles SDK 2.3 | FastMCP 4 (eigenes Paket) | FastMCP bringt viele Zusatzfunktionen und rund 20 weitere Pakete. Für vier Werkzeuge mit Token-Prüfung reicht das SDK. |
| Token für MCP | eigenes, kurzlebiges Token | API-Token weiterreichen | Weiterreichen verbietet die MCP-Spezifikation. |
| Ausstellung | API stellt aus | Keycloak oder Entra ID als echter Authorization Server | Für die lokale Demo ohne Infrastruktur. In Produktion kommt das Token aus dem zentralen Identitätsdienst, etwa per Token Exchange (RFC 8693). |
| Transport | stdio als Standard, HTTP optional | nur HTTP | stdio braucht keinen zweiten Dienst und ist für die Entwicklung am einfachsten. |
| Sitzungen | zustandslos | Sitzungen mit Ereignisspeicher | Unsere Aufrufe sind kurz und brauchen keine Benachrichtigungen vom Server. |

## Fragen im Vorstellungsgespräch

**„Was ist Token Passthrough, und warum ist das schlecht?“**
Ein Dienst reicht das Token, das er selbst bekommen hat, einfach an den nächsten Dienst weiter. Dann kann jeder Dienst in der Kette mit diesem Token überall hin, wo es gilt. Besser ist: Jeder Dienst bekommt ein eigenes Token, das nur für ihn gilt (Audience) und kurz läuft.

**„Was macht ein Resource Server bei OAuth?“**
Er stellt keine Tokens aus. Er prüft nur: Ist die Signatur echt, ist das Token für mich bestimmt, ist es noch gültig? Danach entscheidet er mit Rolle und Team, was erlaubt ist.

**„Warum zeigt der Server Fehlermeldungen nicht einfach an?“**
Fehlermeldungen können Pfade, Datenbanknamen oder Teile von Daten enthalten. Das MCP-SDK 2 gibt deshalb nur bewusst freigegebene Meldungen weiter. Bei uns sind das kurze deutsche Texte ohne Inhalte aus der Anfrage.

**„Warum stdio und HTTP?“**
stdio ist für die lokale Entwicklung am einfachsten und braucht keinen offenen Port. HTTP braucht man, sobald andere Systeme die Werkzeuge nutzen sollen, etwa ein Java-Backend oder ein zweiter Agent.

**„Was fehlt noch für den Betrieb?“**
Ein echter Identitätsdienst statt des gemeinsamen Schlüssels, TLS vor dem MCP-Server, und eine Prüfung, ob ein Benutzer in den letzten fünf Minuten gesperrt wurde. Das steht als Grenze in der Doku.
