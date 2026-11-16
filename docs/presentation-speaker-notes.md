# Sprechertext: Secure Enterprise AI Assistant (v2.1)

Geplant für ruhiges Sprechen, zusammen etwa neun Minuten. Regiehinweise in eckigen Klammern
werden nicht vorgelesen.

## Folie 1: Secure Enterprise AI Assistant

**Zielzeit:** 0:40 Minuten

Guten Tag. Ich stelle den Secure Enterprise AI Assistant vor. Er unterstützt die
Kreditsachbearbeitung der NovaBank Financial Services AG. Diese Bank gibt es nicht: Alle Fälle,
Personen, Richtlinien und Regeln sind synthetisch. Das System läuft vollständig lokal auf einem
MacBook mit einem Sprachmodell mit neun Milliarden Parametern. Gezeigt wird der Stand
Version 2.1.

## Folie 2: Fakten aus Code, Sprache aus dem Modell

**Zielzeit:** 0:55 Minuten

Bei einer Kreditprüfung zählen Zahlen, Regeln und Quellen. Ein reiner Chatbot kann sich
verrechnen, eine Regel übersehen oder eine Quelle erfinden, und es klingt trotzdem überzeugend.
Deshalb trennt das Projekt die Aufgaben streng. Fallakten, Rechnungen und Regelbefunde liefert
geprüfter Code hinter dem Model Context Protocol. Das Sprachmodell formuliert nur aus diesen
Nachweisen. Jede Antwort wird automatisch geprüft, und eine Entscheidung trifft immer ein
Mensch.

## Folie 3: Von v1 zu v2

**Zielzeit:** 0:55 Minuten

Version 1 war mein Abschlussprojekt. Danach habe ich sie selbst kritisch geprüft und die
Schwächen aufgeschrieben. Version 2 entstand in neun Paketen, jedes mit Pull Request, Tag und
Lernnotiz. Einige Ergebnisse: Die Suche findet im Testteil jetzt alle relevanten Dokumente unter
den ersten fünf statt drei Viertel. Der Eingabefilter erkennt im Holdout 15 von 20 Angriffen
statt vorher einem von zwölf. CrewAI mit einem zu großen Modell wurde durch LangGraph mit einem
9B-Modell ersetzt. Und es gibt jetzt Anmeldung, Rollen und ein Audit-Log.

## Folie 4: Architektur

**Zielzeit:** 1:05 Minuten

[Auf das Bild zeigen, von links nach rechts.] Links ist der Zugang: Die deutsche Oberfläche
spricht nur mit der API. Die API prüft das Token, die Rolle und die Rate Limits und schreibt das
Audit-Log. In der Mitte läuft der LangGraph-Ablauf: Eingabefilter, Router, Werkzeugknoten,
Antwort und Antwortprüfung. Wichtig ist: Das Modell wählt keine Werkzeuge. Der Router legt den
Plan fest. Rechts sitzt der MCP-Server mit genau vier Werkzeugen. Er bekommt für jeden Lauf ein
eigenes, fünf Minuten gültiges Token und prüft die Rechte noch einmal. Unten: Ollama läuft
lokal, offene Freigaben liegen in SQLite, Langfuse ist optional.

## Folie 5: Suche und Routing

**Zielzeit:** 0:55 Minuten

Die Suche kombiniert drei Signale: Vektoren, eine klassische Wortsuche und Kennungen wie eine
Dokument-ID. Ich habe vier Embedding-Modelle gemessen. Das kleine qwen3-embedding liegt mit einem
MRR von 0,98 vorn. Die Suche filtert vor dem Ranking; vertrauliche Dokumente können das Ergebnis
also nicht beeinflussen. Ist keine Fundstelle gut genug, sagt das System „keine Antwort“ und ruft
das Modell gar nicht erst auf. Der Router erkennt im Testteil alle 24 Anfragen richtig, in acht
Millisekunden und ohne Sprachmodell.

## Folie 6: Antwortprüfung und Vier-Augen-Freigabe

**Zielzeit:** 1:00 Minuten

Jede Zahl und jede Dokument-ID in einer Antwort muss in den Nachweisen stehen, und eine
Richtlinienaussage braucht eine Quelle. Findet die Prüfung Mängel, bekommt das Modell einen
zweiten Versuch mit der Mängelliste. Scheitert auch der, baut der Code die Antwort selbst aus den
Daten. Eine Entscheidungsvorlage schreibt das Modell gar nicht. Sie entsteht aus den MCP-Daten
und pausiert dann. Freigeben darf nur eine zweite prüfende Person, nicht die Person, die die
Vorlage angefordert hat.

## Folie 7: Praxisbeispiel CASE-00031

**Zielzeit:** 0:55 Minuten

Ein Beispiel: Für CASE-00031 rechnet der Finanzrechner eine Rate von 570,64 Euro. Die
Schuldendienstquote steigt von 28,41 auf 44,95 Prozent. Damit liegt sie über der Prüfschwelle
von 40 Prozent, und RULE-005 ist nicht bestanden. Die anderen neun Regeln sind bestanden. Die
Empfehlung lautet deshalb: manuelle Prüfung. Im echten Lauf hat die anfragende Person versucht,
ihre eigene Vorlage freizugeben, und wurde abgewiesen. Eine zweite Person hat dann freigegeben.
Beides steht im Protokoll.

## Folie 8: Sicherheit

**Zielzeit:** 0:55 Minuten

Rechte werden im Code geprüft, nie im Prompt. Sachbearbeitung sieht nur Fälle des eigenen
Teams; ein fremder Fall sieht aus wie ein unbekannter. Die API reicht ihr Token nie weiter,
sondern stellt für MCP ein eigenes aus. Dokumenttexte stehen im Prompt als markierte Daten, und
ein Eingabefilter fängt bekannte Angriffe ab. Er ist aber nur eine Schicht. Das Audit-Log ist
mit einer Hash-Kette gesichert, und alle Daten bleiben auf dem Rechner.

## Folie 9: Qualität ehrlich gemessen

**Zielzeit:** 1:00 Minuten

Mit dem echten Modell habe ich 17 Fragen gemessen. Im dritten Lauf enthalten 13 von 15
beantwortbaren Antworten alle erwarteten Fakten, und beide Fragen ohne Antwort werden richtig
abgelehnt. Von Hand geprüft sind 11 von 14 Antworten vollständig belegt. Ohne Suche beantwortet
dasselbe Modell nur eine von zehn Richtlinienfragen richtig. Ehrlich gesagt: Die Fragen stammen
von mir, und der dritte Lauf kam nach Korrekturen, er ist also optimistisch. Dazu kommen 321
automatisierte Tests, vier Live-Tests und ein Experiment in Langfuse.

## Folie 10: Fazit und Grenzen

**Zielzeit:** 0:45 Minuten

Das Projekt zeigt, wie man ein Sprachmodell kontrolliert einsetzt: wenige Rechte für das Modell,
geprüfte Antworten, eine Freigabe durch Menschen, alles lokal und auf Deutsch. Es ist kein
Bankprodukt. Die Daten sind erfunden, es fehlen ein Identity Provider und unabhängige
Testsätze. Die nächsten Schritte wären ein Reranker, größere geprüfte Testsammlungen und eine
echte Single-Sign-on-Anbindung. Vielen Dank.
