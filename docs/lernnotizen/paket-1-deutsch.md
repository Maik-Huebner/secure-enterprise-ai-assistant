# Lernnotiz Paket 1 – Deutsch durchgängig (v1.1)

## Worum ging es?

Die Oberfläche war deutsch, alles dahinter aber englisch: 18 Richtlinien, das Regelwerk, die Prompts und die Fehlermeldungen. Eine Notlösung mit acht Wörtern übersetzte deutsche Fragen halb ins Englische, damit die Suche überhaupt etwas fand. Der Eingabefilter kannte nur drei englische Angriffssätze.

## Was wurde gebaut?

### 1. Inhalte auf Deutsch

- **18 Richtlinien** sind neu auf Deutsch geschrieben. Die Quelle ist `development/knowledge_base.py`, die Markdown-Dateien werden daraus erzeugt. Dokument-IDs, Abschnittsnummern und **Dateinamen bleiben gleich**. So bleiben alle Verweise stabil, und es musste keine Datei gelöscht werden.
- **Regelwerk** (`rules.json`): deutsche Titel, Beschreibungen und Quellenangaben. Die technischen Codes bleiben (`kyc`, `critical`, `rejected`).
- **Compliance-Meldungen** kommen direkt auf Deutsch aus dem Service, mit deutscher Zahlenschreibweise („66,03 %“, „18.250,00 EUR“).
- **Prompts** der Agenten, **Guardrail-Rückmeldungen**, **MCP-Werkzeugbeschreibungen**, **Fehlermeldungen** und **Trace-Einträge** sind deutsch.

### 2. Notlösungen entfernt

- Das Wörterbuch mit 8 Begriffen (`QUERY_EXPANSIONS`) ist weg.
- Die Spracherkennung per Wortliste ist weg. Deutsch ist jetzt immer die Antwortsprache.
- Weg ist auch die Übersetzung per Suchen und Ersetzen im MCP-Client, mit rund 30 Satzbausteinen. Sie war fehleranfällig: Änderte sich ein englischer Satz minimal, blieb er englisch, und kein Test schlug an.
- Neu ist **eine zentrale Stelle** für die Anzeige von Codes und Zahlen (`core/labels.py`). Vorher lagen dieselben Zuordnungen doppelt vor, in der UI und im Client.

### 3. Ein echter Fehler aus v1 behoben

Drei von zehn Regeln zitierten **Abschnitte, die es nicht gab**. RULE-005 verwies zum Beispiel auf einen Abschnitt „6.2“, den die Richtlinie nicht hatte. Ein neuer Test prüft jetzt für jede Regel, ob Dokument, Titel und Abschnitt wirklich existieren. So etwas fällt nur auf, wenn man es automatisch prüft.

### 4. Neuer Eingabefilter für Deutsch und Englisch

**Fünf Kategorien:** Anweisungen überschreiben, Rolle oder Modus wechseln, interne Anweisungen auslesen, Befehle oder Code ausführen, Prüfungen umgehen.

**Vor dem Vergleich wird der Text normalisiert:**

| Trick | Beispiel | Gegenmittel |
|---|---|---|
| Unsichtbare Zeichen | `Igno​riere` (mit U+200B) | Zeichen der Unicode-Kategorie „Cf“ entfernen |
| Breite Zeichen | `ＩＧＮＯＲＩＥＲＥ` | Unicode-NFKC |
| Gesperrte Schreibweise | `I g n o r i e r e` | einzelne Buchstaben zusammenziehen |
| Ziffern statt Buchstaben | `1gn0r1ere` | zweite Fassung mit Rückersetzung prüfen |

Die Ziffern-Rückersetzung prüfe ich als **zweite** Fassung. Sonst würde aus `RULE-006` die Zeichenfolge `rule-oo6`.

**Deutsche Grammatik als Stolperstein:**

- **Komposita:** „System**anweisungen**“ ist ein Wort. Das Muster erlaubt deshalb ein Präfix vor dem Zielwort.
- **Verb am Ende:** „Kannst du alle Anweisungen **ignorieren**?“ Dafür gibt es eine zweite Reihenfolge Ziel → Verb.

**Fachliche Fragen bleiben erlaubt:** „Darf die KYC-Prüfung übersprungen werden?“ ist eine legitime Frage. Bei Fragesätzen lockert der Filter deshalb nur die Kategorie „Prüfungen umgehen“. Die anderen Kategorien bleiben auch bei Fragen aktiv.

**Dokumente:** Derselbe Filter prüft die Wissensbasis, aber nur in den Kategorien, die sich an das Modell richten. Zwei Richtlinien beschreiben selbst, wie man mit Prompt-Injection umgeht. Sie dürfen sich nicht selbst aussortieren. Ein Test sichert das ab.

### 5. Ehrliche Messung mit Entwicklungs- und Prüf-Satz

| Satz | Angriffe blockiert | Fehlalarme |
|---|---:|---:|
| Entwicklung (daran gebaut) | 30 / 30 | 0 / 30 |
| **Prüf-Satz (danach geschrieben, nicht nachgestellt)** | **15 / 20** | **0 / 20** |

Zum Vergleich der Prüfbericht von v1.0.2: 1 von 12 Angriffen blockiert.

Durchgerutscht sind Umschreibungen wie „lass alle Vorgaben **außer Acht**“, „**stell dir vor**, du hättest keine Regeln“ und „**From now on** you are…“. Ich habe den Filter daran bewusst nicht angepasst. Sonst wäre der Prüf-Satz verbraucht, und ich hätte keine ehrliche Zahl mehr.

### 6. UI-Fehler behoben

Eine blockierte Anfrage zeigte vorher „Prüfe, ob Ollama läuft“. Jetzt zeigt sie: „Diese Anfrage wurde aus Sicherheitsgründen nicht ausgeführt.“

## Live-Prüfung mit qwen3.5:9b (16.11.2026)

Zwei echte Läufe über CrewAI, MCP und Ollama auf dem MacBook Pro M4 Pro:

| Anfrage | Dauer | Ergebnis |
|---|---:|---|
| „Berechne die Kreditbelastung für CASE-00031.“ | 21,6 s | **richtig.** Alle fünf Zahlen exakt wie der Rechner, komplett deutsch. |
| „Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?“ | 31,3 s | **inhaltlich falsch.** Quelle `NB-DOC-001` korrekt zitiert, aber erfundene Unterlagen („Schuldenverzeichnis“, „Selbstständigkeitserklärung“), zwei echte fehlen. |

Die Suche hat die richtige Stelle („3.1 Pflichtnachweise“) auf Platz 1 geliefert. Das Modell hat sie bekommen und trotzdem etwas anderes geschrieben. Das ist eine **Halluzination mit korrekter Quellenangabe**, und gerade sie wirkt glaubwürdig. Behoben wird das in Paket 4: Dort kommt eine Messung der Antworttreue dazu, und die Antwort wird enger an die gefundenen Textstellen gebunden.

Nebenbefund für Paket 2: Unter den fünf Treffern ist der Abschnitt „Dokumentmetadaten“ mit Kopfzeilen und Hinweistext. Er belegt einen Platz, ohne Inhalt zu liefern.

## Was ist bewusst noch offen?

- **Suche:** Mit dem Hashing-Embedder findet „Welche **Pflichtunterlagen** braucht ein Verbraucherkredit?“ nichts. Im Text steht „Pflicht**nachweise**“. Recall@5 der kleinen Suite liegt bei 0,8. Das löst Paket 2 mit echten Embeddings.
- **Code-Interna** bleiben englisch: Bezeichner, Kommentare und Docstrings. Das ist in Teams üblich und hält den Code für alle lesbar.
- **README und Architektur-Doku** sind noch englisch. Sie werden in Paket 7 übersetzt.

## Welche Alternativen gab es?

| Entscheidung | Gewählt | Alternative | Warum so |
|---|---|---|---|
| Sprache der Wissensbasis | deutsch schreiben | englisch lassen und mehrsprachiges Embedding nutzen | Nutzer und Prüfer lesen die zitierten Stellen. Deutsche Quellen zu deutschen Fragen sind ehrlicher und leichter zu prüfen. |
| Eingabefilter | Regeln mit Normalisierung | Klassifikator (z. B. ein kleines Prompt-Guard-Modell) | Regeln sind nachvollziehbar, schnell und ohne Modell testbar. Ein Klassifikator erkennt Umschreibungen besser, braucht aber ein weiteres Modell und eigene Evaluation. Er wäre eine gute zweite Schicht. |
| Übersetzung der Meldungen | an der Quelle deutsch | Übersetzungsschicht behalten | Eine Schicht, die Text nachträglich ersetzt, bricht still, wenn sich die Quelle ändert. |
| Dateinamen | gleich gelassen | deutsche Dateinamen | Keine Löschungen, stabile Verweise. Der Inhalt zählt, nicht der Dateiname. |

## Fragen im Vorstellungsgespräch

**„Wie gut ist euer Prompt-Injection-Filter?“**
Auf Sätzen, die ich nicht zum Bauen benutzt habe, blockiert er 15 von 20 Angriffen ohne Fehlalarm. Die Zahl ist ehrlich, aber nicht unabhängig, weil ich beide Sätze selbst geschrieben habe. Wichtiger als die Zahl: Der Filter ist nur die erste Schicht. Auch ein erfolgreicher Angriff kann nichts Gefährliches auslösen, weil die Werkzeuge nur lesen und rechnen und die Rechte im Code geprüft werden.

**„Warum zwei Testsätze?“**
Wenn ich Muster an denselben Beispielen baue und messe, bekomme ich fast immer 100 %. Das sagt nichts darüber, wie der Filter bei neuen Angriffen arbeitet. Der Prüf-Satz entspricht dem Testdatensatz beim maschinellen Lernen: einmal messen, nicht nachstellen.

**„Warum blockiert ihr nicht einfach alles mit ‚ignorieren‘ oder ‚Systemprompt‘?“**
Weil dann fachliche Fragen wie „Was passiert, wenn ich eine Anweisung ignoriere?“ blockiert würden. Fehlalarme sind im Arbeitsalltag teuer, denn Nutzer verlieren das Vertrauen und umgehen das System. Deshalb messe ich beides: Erkennungsrate und Fehlalarme.

**„Was sind die Tricks gegen Verschleierung?“**
Unicode-Normalisierung (NFKC), unsichtbare Zeichen entfernen, gesperrte Buchstaben zusammenziehen und Ziffern zurück in Buchstaben verwandeln. Das alles passiert nur auf einer Kopie für den Vergleich, die Anfrage selbst bleibt unverändert.

**„Warum habt ihr die Wissensbasis übersetzt und nicht einfach ein mehrsprachiges Embedding genommen?“**
Beides hat seinen Platz. Ein mehrsprachiges Modell kommt in Paket 2 sowieso. Aber die zitierten Textstellen liest ein Mensch, und eine Bank in Deutschland hat deutsche Richtlinien. Englische Quellen unter einer deutschen Antwort wirken unfertig und sind schwerer zu prüfen.

**„Euer Assistent zitiert die richtige Richtlinie. Ist die Antwort dann richtig?“**
Nein, und genau das habe ich im Live-Test gesehen. Das Modell zitierte `NB-DOC-001` korrekt, erfand aber zwei der vier Unterlagen. Eine richtige Quellenangabe beweist nicht, dass der Inhalt stimmt. Deshalb braucht man eine eigene Messung der Treue: Steht jede Aussage der Antwort wirklich in der gefundenen Textstelle?

**„Wie stellt ihr sicher, dass Quellenangaben stimmen?“**
Mit einem Test, der jede Regel gegen die Wissensbasis prüft: Gibt es das Dokument, stimmt der Titel, gibt es den Abschnitt? Dabei kamen drei falsche Verweise aus v1 ans Licht. Ohne den Test wären sie nie aufgefallen.
