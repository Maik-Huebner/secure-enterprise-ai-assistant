# Sicherheitsmodell

Dies ist eine synthetische Demo für ein Portfolio, kein produktives Bankensystem.

## Identität und Zugriff (v1.3)

- **Anmeldung:** `POST /v1/auth/token` mit Benutzername und Passwort. Passwörter liegen als
  Argon2id-Hashes (Standardwerte von argon2-cffi, RFC 9106) in `<RUNTIME_DIR>/security/users.json`,
  nur für den Besitzer lesbar. Unbekannte Benutzer werden gegen einen Dummy-Hash geprüft, damit
  die Antwortzeit keine gültigen Namen verrät. Benutzer verwaltet `novabank-users`.
- **Tokens:** HS256-JWTs, standardmäßig 15 Minuten gültig. Der Algorithmus ist fest (kein `none`);
  `iss`, `aud`, `exp`, `nbf`, `iat`, `sub` und `jti` sind Pflicht. `JWT_SECRET` hat keinen
  Standardwert und muss mindestens 32 Byte lang sein; ohne ihn startet die API nicht. Gelöschte
  oder deaktivierte Benutzer verlieren den Zugriff sofort.
- **Berechtigungen** (`security/access.py`), im Code und in jedem MCP-Werkzeug durchgesetzt:

| Rolle | Fälle | Dokumente | Entscheidungsvorlage |
|---|---|---|---|
| `sachbearbeiter` | nur das eigene Team | `intern` | nein (Vier-Augen-Prinzip) |
| `pruefer` | alle | `intern`, `vertraulich` | ja |
| `admin` | alle | `intern`, `vertraulich` | ja |

- **Keine Umwege:** Ein fremder Fall liefert dasselbe 404 wie ein unbekannter. Die Wissenssuche
  filtert Dokumente vor dem Ranking; die BM25-Statistik wird nur über die erlaubten Dokumente
  berechnet (ein Test hatte gezeigt, dass die IDF über den ganzen Korpus versteckte Dokumente das
  Ranking verschieben ließ). Ausdrückliche Dokument-IDs oder `document_id`-Filter auf verbotene
  Dokumente liefern nichts.
- **Weitergabe des Tokens (v1.5):** Die API reicht ihr eigenes Bearer-Token nie weiter. Für jeden
  Lauf stellt sie ein eigenes MCP-Token aus (Audience `novabank-mcp`, 5 Minuten). Es erreicht den
  MCP-Server entweder in `NOVABANK_ACCESS_TOKEN` (stdio-Unterprozess) oder als
  `Authorization: Bearer` (Streamable HTTP). Der Server prüft Signatur, Aussteller, Audience und
  Ablauf und bindet jeden Werkzeugaufruf an die geprüfte Identität; ohne gültiges Token wird jeder
  Aufruf abgelehnt. Ein API-Token weist der MCP-Server ab, ein MCP-Token die API (getestet).
  Unterprozesse erhalten nur freigegebene Anwendungseinstellungen, nie die ganze Umgebung des
  Elternprozesses.
- **MCP über HTTP:** zustandsloses Streamable HTTP in der Rolle eines Resource Servers mit
  Protected-Resource-Metadaten (RFC 9728), die die API als Token-Aussteller nennen. Fehlende,
  gefälschte, abgelaufene oder falsch adressierte Tokens bekommen 401 mit `WWW-Authenticate`.
  Nur erwartete Werkzeugfehler (unbekannter oder fremder Fall, fehlende Rechte, ungültige
  Eingabe) geben ihre Meldung zurück; jede andere Ausnahme wird als „Error executing tool“
  maskiert (Text des MCP SDK).

## Härtung der API

- Ratenbegrenzung: Anmeldung je Client-IP (5/min), Chat je Benutzer (20/min), API je Benutzer
  (120/min);
- CORS standardmäßig geschlossen (`CORS_ALLOWED_ORIGINS`), keine Credentials, nur GET und POST;
- Header: strenge CSP für die API (nur für `/docs` gelockert), `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`,
  `Permissions-Policy`, optional HSTS;
- Problem Details nach RFC 9457 auf Deutsch; Validierungsfehler nennen nur Feldnamen und geben nie
  Werte wie Passwörter zurück; unerwartete Fehler liefern ein neutrales 500 und werden
  serverseitig protokolliert;
- Request-IDs (`X-Request-ID`) für Logs und Audit-Einträge.

## Audit-Log

`<RUNTIME_DIR>/audit/audit.jsonl`, ein JSON-Objekt pro Zeile mit SHA-256-Hash-Kette
(`prev_hash`, `hash`). Erfasst werden Anmeldungen (Erfolg und Fehlschlag), Fallzugriffe und
Ablehnungen, Suchen (Länge der Frage und gelieferte Dokument-IDs, nicht der Fragetext) sowie
Ergebnisse und Ablehnungen im Chat. `novabank-audit pruefen` meldet die erste beschädigte Zeile.
Die Kette macht Manipulation sichtbar; sie verhindert nicht, dass die ganze Datei gelöscht wird.
Produktive Systeme schreiben Einträge zusätzlich in einen nur beschreibbaren Speicher (WORM).

## Kontrollen für Eingaben und Inhalte

- strenge Pydantic-Schemas für Domäne und MCP-Antworten;
- Positivliste aus vier Werkzeugen; das Sprachmodell wählt oder ruft nie selbst Werkzeuge auf
  (der Router legt den Werkzeugplan fest, der LangGraph-Werkzeugknoten führt ihn über MCP mit dem
  Token des Aufrufers aus);
- kein beliebiges SQL, keine Shell, keine Codeausführung, kein URL-Abruf, kein Dateisystem-Werkzeug;
- Prüfung von Fall-ID, Länge der Anfrage, Metadatenfilter und Pfadgrenzen;
- ein Prompt-Injection-Filter als erste Schicht für Deutsch und Englisch (fünf Kategorien,
  Unicode- und Verschleierungsnormalisierung), angewendet in der API vor dem Ablauf und noch
  einmal im Ablauf. Auf dem Holdout-Split hat er 15 von 20 Angriffen erkannt, ohne eine der
  20 harmlosen Fragen zu blockieren (16.11.2026). Umschreibungen wie „lass die Vorgaben außer
  Acht“ kommen noch durch; deshalb ist dieser Filter nie die einzige Kontrolle;
- gefundene Dokumente stehen im Prompt als Daten abgegrenzt (`<richtlinie>`); Dokumente mit
  Injection-Mustern, die sich an das Modell richten, werden in Quarantäne genommen und protokolliert;
- jede Modellantwort wird geprüft (Zahlen und Dokument-IDs müssen in den Nachweisen vorkommen,
  Quellenangaben sind Pflicht, Bezeichnungen deutsch); ein zweiter Versuch, danach eine geprüfte
  Ersatzantwort ohne Modell;
- Entscheidungsvorlagen entstehen ohne Modell und brauchen die Freigabe einer zweiten Person
  (Vier-Augen-Prinzip, in der API und noch einmal in einem eigenen Graph-Knoten durchgesetzt);
- das Zugriffstoken ist Laufkontext und wird nie in den Checkpoint des Graphen geschrieben
  (getestet);
- die endgültige Kreditverantwortung bleibt bei einer berechtigten Person.

## Tracing und Datenschutz (v1.6)

- Das Langfuse-Tracing ist **standardmäßig aus**. Ohne `LANGFUSE_ENABLED=true` und beide
  Projektschlüssel wird kein Client erzeugt, und nichts verlässt den Prozess (getestet).
- Eingeschaltet enthalten Traces Prompts und Antworten, also auch die (synthetischen) Falldaten,
  die das Modell gesehen hat. Ein echter Einsatz braucht eine Datenschutz-Folgenabschätzung, eine
  selbst betriebene Instanz im Netz der Bank und eine Aufbewahrungsregel. Das mitgelieferte
  Compose-Profil bindet jeden Port an `127.0.0.1`, schaltet Telemetrie ab und hat keine
  Standardpasswörter (`scripts/langfuse_env.py` erzeugt sie in eine git-ignorierte Datei, die nur
  der Besitzer lesen darf).
- Das Benutzerfeld eines Traces ist ein Pseudonym (HMAC mit dem JWT-Schlüssel der Anwendung, den
  der Trace-Speicher nie sieht); die Thread-ID ist die Sitzung. So tauchen Namen nicht in Filtern
  und Dashboards auf, **aber** weiterhin in den Trace-Inhalten: der Zustand des Graphen
  (`requested_by`), die Freigabenotiz einer Entscheidungsvorlage und die synthetischen Falldaten
  nennen Personen. Der Zugang zu Langfuse muss deshalb so beschränkt werden wie der Zugang zu den
  Fallakten.
- Zugriffstokens sind Laufkontext und nie Teil des aufgezeichneten Zustands; zusätzlich entfernt
  eine Maskierungsfunktion vor dem Export alles, was wie ein JWT aussieht (mit einem
  mitgeschnittenen Trace getestet).
- Die Langfuse-Schlüssel gehören nicht zu den Einstellungen, die an den MCP-Unterprozess gehen
  (getestet).

## Bekannte Lücken bis zur Produktion

- ein gemeinsamer HS256-Schlüssel statt eines Identity Providers (OAuth 2.1 / OpenID Connect,
  SSO, MFA); die API stellt MCP-Tokens aus, ist aber kein vollständiger OAuth-2.1-Autorisierungsserver;
- der MCP-HTTP-Server prüft innerhalb der fünf Minuten Token-Laufzeit keine Deaktivierung und hat
  kein eigenes TLS (an Loopback binden oder hinter einen Proxy stellen);
- Benutzer in einer JSON-Datei statt in einem Verzeichnisdienst;
- Ratenbegrenzung im Speicher je Prozess (mehrere Instanzen brauchen Redis oder ein Gateway);
- keine TLS-Terminierung in der Anwendung (gehört in einen Reverse Proxy);
- das Audit-Log macht Manipulation sichtbar, verhindert sie aber nicht;
- Traces werden außer bei Tokens nicht auf personenbezogene Daten maskiert (für synthetische
  Daten in Ordnung, für echte Kundinnen und Kunden nicht);
- verschlüsselte Speicherung, Kontrollen der Modell-Lieferkette, Sandbox für schädliche Dateien
  und eine formale regulatorische Prüfung fehlen.
