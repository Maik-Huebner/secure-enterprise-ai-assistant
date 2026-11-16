# Lernnotiz Paket 3 – FastAPI-Backend mit Sicherheit (v1.3)

## Worum ging es?

Bisher gab es nur eine Gradio-Oberfläche, die alles im selben Prozess erledigt hat. Es gab keine Anmeldung und keine Rollen. Jeder, der die Oberfläche erreichte, sah jeden Fall und jedes Dokument. Eine Agentur mit PHP- und Java-Teams braucht außerdem eine **Schnittstelle**, über die andere Systeme die Funktionen nutzen können.

## Was wurde gebaut?

### 1. REST-API mit FastAPI

| Endpunkt | Wofür |
|---|---|
| `POST /v1/auth/token` | Anmeldung, liefert ein Token |
| `GET /v1/me` | eigene Rolle und Rechte |
| `GET /v1/cases`, `/v1/cases/{id}` | sichtbare Fälle |
| `.../financials`, `.../compliance` | Kennzahlen und Regelergebnisse |
| `POST /v1/search` | Suche in den Richtlinien |
| `POST /v1/chat` | der Assistent |
| `GET /health`, `/ready` | Lebenszeichen und Bereitschaft (für Docker und Kubernetes) |

Unter `/docs` steht die **OpenAPI-Dokumentation** zum Ausprobieren. Ein PHP- oder Java-Team kann daraus sogar automatisch einen Client erzeugen.

### 2. Anmeldung: Argon2id und JWT

- **Argon2id** ist der empfohlene Algorithmus für Passwort-Hashes (OWASP). Er ist absichtlich langsam und speicherhungrig, damit Angreifer gestohlene Hashes nicht schnell durchprobieren können.
- **Unbekannte Benutzer** werden gegen einen Platzhalter-Hash geprüft. So dauert die Antwort gleich lang, und man kann nicht an der Antwortzeit erkennen, ob ein Benutzername existiert.
- **JWT** (JSON Web Token) ist ein signiertes Ticket mit Name, Rolle, Team und Ablaufzeit (15 Minuten). Der Algorithmus ist fest auf HS256 eingestellt. Ein bekannter Angriff ist, `"alg": "none"` ins Token zu schreiben. Der wird abgewiesen, ein Test prüft das.
- **Kein Secret im Repository:** `JWT_SECRET` hat keinen Standardwert. Ohne Schlüssel startet die API nicht. Benutzer legst du mit `novabank-users add` an, das Passwort wird verdeckt abgefragt.

### 3. Rollen und Rechte – im Code, nicht im Prompt

| Rolle | Fälle | Dokumente | Entscheidungsvorlage |
|---|---|---|---|
| Sachbearbeitung | nur eigenes Team | intern | nein (Vier-Augen-Prinzip) |
| Prüfung | alle | intern + vertraulich | ja |
| Admin | alle | intern + vertraulich | ja |

**Warum nicht im Prompt?** Ein Prompt wie „Zeige keine vertraulichen Dokumente“ ist eine Bitte an das Sprachmodell, keine Sperre. Mit Prompt-Injection lässt sie sich aushebeln. Eine Prüfung im Code lässt sich nicht überreden.

### 4. Das Token reist bis in die Werkzeuge

```
UI → API (prüft Token) → Flow → CrewAI / Bericht → MCP-Unterprozess (prüft Token erneut) → Werkzeug (prüft Recht)
```

Auch wer die API umgeht und den MCP-Server direkt startet, bekommt ohne gültiges Token nichts. Ein Test macht genau das.

### 5. Keine Umwege

- **Fremde Fälle** liefern dieselbe Antwort wie unbekannte Fälle (404). So kann niemand herausfinden, welche Fall-Nummern es im anderen Team gibt.
- **Vertrauliche Dokumente** werden vor dem Ranking entfernt. Bei echten Embeddings sieht man das gut: Die Sachbearbeitung bekommt auf eine Geldwäsche-Frage „keine Antwort“, die Prüfung bekommt `NB-AML-001`.
- **Getestete Umwege:** direkter Filter `document_id=NB-AML-001`, Dokument-ID in der Frage, direkter MCP-Aufruf, gefälschtes Token und Token eines gelöschten Benutzers.

### 6. Schutz der Schnittstelle

- **Rate Limiting:** 5 Anmeldeversuche pro Minute und IP, 20 Chat-Anfragen pro Minute und Benutzer.
- **CORS** ist geschlossen: Andere Webseiten dürfen die API nicht aus dem Browser aufrufen.
- **Sicherheitsheader:** Content-Security-Policy, kein Einbetten in fremde Seiten (`X-Frame-Options`), kein Zwischenspeichern (`no-store`).
- **Fehlerantworten** im Standardformat RFC 9457 auf Deutsch, ohne interne Details. Validierungsfehler nennen nur die Feldnamen, nie den Inhalt, sonst stünde beim Login das Passwort in der Antwort.

### 7. Audit-Log mit Hash-Kette

Jeder Eintrag enthält den Hash des vorherigen. Wer eine Zeile ändert, zerstört die Kette ab dieser Stelle, und `novabank-audit verify` zeigt die Zeile an. Gespeichert werden **keine Passwörter und keine Fragetexte**, nur Länge, Fall-ID und Dokument-IDs.

### 8. Gradio ist jetzt nur noch Client

Die Oberfläche meldet sich an der API an und schickt jede Anfrage mit dem Token. Sie hat keinen direkten Zugriff mehr auf Fälle, Dokumente oder Werkzeuge.

## Was ich beim Bauen gefunden habe

- **Der MCP-Unterprozess bekam keine Einstellungen.** Das MCP-SDK gibt dem Unterprozess nur `HOME`, `PATH` und `USER` mit. In der CI hätte der Server deshalb versucht, Ollama zu erreichen. Die Lösung ist eine **Positivliste** der eigenen Einstellungen. Fremde Geheimnisse aus der Umgebung werden so bewusst nicht weitergegeben.
- **`from __future__ import annotations` vertragen sich nicht mit FastAPI**, wenn Abhängigkeiten innerhalb einer Funktion definiert sind. FastAPI konnte sie nicht auflösen und hat 422 statt 401 geliefert. Gefunden haben das die Sicherheitstests.
- **Meine eigene Audit-Regel** hat zuerst falsch angeschlagen: `\s*` passt auch auf einen Zeilenumbruch. Ein Test sichert die Regel jetzt ab.

## Live-Prüfung (16.11.2026, M4 Pro, echte Modelle)

- Entscheidungsvorlage über die API: korrekt, 11,2 s beim ersten Aufruf (Kaltstart).
- Wissensfrage über die API: In diesem Lauf nannte das Modell die vier richtigen Unterlagen. In Paket 1 hatte es zwei erfunden. Das ist ein einzelner Lauf, keine Messung. Die Messung der Treue kommt in Paket 4.
- 0 Fehler im API-Log, Audit-Kette intakt.

## Welche Alternativen gab es?

| Entscheidung | Gewählt | Alternative | Warum so |
|---|---|---|---|
| Token-Signatur | HS256 mit einem Schlüssel | RS256 mit Schlüsselpaar | Ein Dienst stellt aus und prüft. RS256 lohnt sich, wenn viele Dienste prüfen, aber nur einer ausstellen darf. |
| Anmeldung | eigene Benutzerliste | OAuth 2.1 / OpenID Connect (Keycloak, Entra ID) | Für eine lokale Demo ohne Infrastruktur. In einer Bank kommt die Anmeldung aus dem zentralen Identitätsdienst (SSO). Das steht als Grenze in der Doku. |
| Rate Limiting | eigene, kleine Klasse | slowapi, Redis, API-Gateway | Keine neue Abhängigkeit. Bei mehreren Instanzen muss der Zähler zentral liegen (Redis oder Gateway). |
| Audit-Log | Datei mit Hash-Kette | Datenbank, SIEM, WORM-Speicher | Zeigt das Prinzip. In Produktion gehen die Einträge zusätzlich an einen Speicher, der nicht änderbar ist. |
| Fremde Fälle | 404 wie unbekannt | 403 „verboten“ | 403 würde verraten, dass der Fall existiert. |

## Fragen im Vorstellungsgespräch

**„Warum prüft ihr die Rechte auch noch im MCP-Werkzeug, wenn die API schon prüft?“**
Verteidigung in der Tiefe. Die Werkzeuge können auch anders aufgerufen werden, zum Beispiel direkt über MCP oder später über HTTP von einem anderen Agenten. Wenn nur die API prüft, ist jeder andere Weg offen.

**„Was ist ein Seitenkanal bei RAG?“**
Wenn man Dokumente erst nach dem Ranking ausfiltert, beeinflussen verbotene Dokumente trotzdem die Ergebnisse. Etwa so: „keine Antwort“ statt einer Antwort, oder eine andere Reihenfolge. Daraus kann man ableiten, dass es ein Dokument gibt. Bei uns kam der Effekt sogar über die BM25-Statistik herein, das hat ein Test gezeigt.

**„Warum ist das Token nur 15 Minuten gültig?“**
Ein gestohlenes Token ist dann nur kurz nutzbar. Zusätzlich prüft die API bei jeder Anfrage, ob der Benutzer noch aktiv ist. Wer gelöscht wird, verliert den Zugang sofort und nicht erst nach Ablauf.

**„Wie verhindert ihr den JWT-Angriff mit ‚alg: none‘?“**
Der erlaubte Algorithmus steht fest im Code (`algorithms=["HS256"]`). Was im Token steht, spielt keine Rolle. Ein Test schickt ein Token mit `alg: none` und erwartet 401.

**„Warum keine Passwörter oder Fragen im Audit-Log?“**
Das Audit-Log soll nachweisen, wer wann was getan hat. Es soll nicht selbst zum Datenleck werden. Fragen können Kundendaten enthalten. Die Länge der Frage, die Fall-ID und die gefundenen Dokument-IDs reichen für die Nachvollziehbarkeit.

**„Was würdest du für den echten Betrieb noch ändern?“**
Anmeldung über den zentralen Identitätsdienst (OpenID Connect mit MFA), Benutzer aus dem Verzeichnisdienst, Rate Limiting im Gateway, TLS am Reverse Proxy und Audit-Einträge in einen nicht änderbaren Speicher.
