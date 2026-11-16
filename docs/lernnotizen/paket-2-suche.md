# Lernnotiz Paket 2 – Echtes Embedding und bessere Suche (v1.2)

## Worum ging es?

Die Suche war bisher eine reine Wortsuche: Der „Hashing-Embedder“ zählt Wörter, versteht aber keine Bedeutung. Deutsche Komposita wie „Pflicht**unterlagen**“ statt „Pflicht**nachweise**“ hat er nicht gefunden. Der Suchindex wurde in jedem MCP-Prozess neu berechnet, und der Router erkannte nur feste Wortlisten.

## Was wurde gebaut?

### 1. Echte Embeddings über Ollama

Ein **Embedding** verwandelt einen Text in eine Liste von Zahlen (einen Vektor). Texte mit ähnlicher Bedeutung bekommen ähnliche Vektoren, auch wenn sie andere Wörter benutzen. So findet „Pflichtunterlagen“ den Abschnitt „Pflichtnachweise“.

Ich habe drei lokale, mehrsprachige Modelle gemessen, alle über Ollama:

| Modell | Recall@5 | MRR | Fragen ohne Antwort richtig | Latenz |
|---|---:|---:|---:|---:|
| Hashing (vorher) | 0,75 | 0,60 | 1,00 | 0,2 ms |
| bge-m3 | 1,00 | 0,92 | 1,00 | 25 ms |
| **qwen3-embedding:0.6b** | **1,00** | **0,98** | **1,00** | 32 ms |
| embeddinggemma | 0,95 | 0,90 | 1,00 | 21 ms |

**Gewählt: `qwen3-embedding:0.6b`.** Es ist am genauesten, sortiert am besten (MRR) und ist mit gut 0,6 GB klein.

**Wichtiges Detail:** `qwen3-embedding` und `embeddinggemma` erwarten laut Modellkarte **unterschiedliche Vorsätze** für Fragen und Dokumente, zum Beispiel `Instruct: … Query:`. Ohne diese Vorsätze arbeiten sie schlechter. Das ist ein typischer Fehler bei RAG-Systemen.

### 2. Persistenter Index mit Manifest

Die Vektoren werden einmal berechnet und gespeichert, zusammen mit einem **Manifest**: Modellname, Dimension, Prüfsumme der Wissensbasis und Version der Zerlegung. Passt beim Start etwas nicht, wird neu gebaut, ein veralteter Index wird nie still benutzt.

- Aufbau: etwa 2 s für 76 Abschnitte, Laden: etwa 0,02 s
- Befehle: `novabank-index rebuild` und `novabank-index status`

### 3. Filter vor dem Ranking (Vorbereitung für Paket 3)

Darf ein Nutzer bestimmte Dokumente nicht sehen, werden sie **vor** der Bewertung entfernt, nicht danach. Sonst könnte jemand über Umwege etwas erfahren, zum Beispiel weil sich die Rangfolge oder die Antwort „keine Antwort“ ändert.

Ein Test hat dabei einen **echten Seitenkanal** gefunden. BM25 berechnet die Seltenheit eines Wortes (IDF) über alle Dokumente. Ein verbotenes Dokument hat also die Reihenfolge der erlaubten verändert. Jetzt wird BM25 für die erlaubte Teilmenge eigens berechnet und zwischengespeichert.

### 4. Teilenummern

Fragen wie „Was steht in NB-RSK-001 Abschnitt 7.4?“ werden per Regel erkannt. Der genannte Abschnitt steht dann sicher oben. Eine Bedeutungssuche allein findet so etwas nicht zuverlässig.

### 5. Weniger Rauschen im Index

Der Kopfbereich jeder Richtlinie (Metadaten und Hinweistext) wurde bisher als eigener Treffer indexiert und belegte einen der fünf Plätze. Jetzt stehen die Metadaten an jedem Abschnitt, und der leere Kopf ist kein Treffer mehr.

### 6. Hybrider Router

- **Fall-ID per Regel**, neu auch „Fall 31“.
- **Absicht:** Kommen eindeutige Schlüsselwörter vor („Entscheidungsvorlage“), entscheiden sie. Sonst wird die Anfrage per Embedding mit **Beispielsätzen** verglichen, ganz ohne Sprachmodell.

| Router | Test |
|---|---:|
| nur Schlüsselwörter | 22/24 |
| nur Bedeutung | 24/24 |
| **hybrid** | **24/24**, im Schnitt 8 ms |

### 7. Ehrliche Evaluation

- **48 Suchfragen** (24 Entwicklung, 24 Test) mit Umformulierungen, Komposita, Teilenummern und 8 Fragen ohne Antwort.
- **49 Routing-Fälle** (25 Entwicklung, 24 Test).
- **Die Schwelle für „keine Antwort“** wird nur auf dem Entwicklungsteil kalibriert, gemessen wird auf dem Testteil.
- Der Benchmark prüft sich selbst: Seine Zahlen müssen mit dem echten Retriever übereinstimmen. Dabei habe ich einen eigenen Fehler gefunden: Der Benchmark hatte nicht berücksichtigt, dass eine Dokument-ID immer als Beleg zählt.
- Zwei Kennzahlen, die fast immer 1,0 waren, sind entfernt.

### 8. Reproduzierbar auf jeder Plattform

Die CI unter Linux hat andere Zahlen gemessen als mein Mac. Der Grund: Bei der Hashing-Suche teilen sich bis zu 75 Abschnitte exakt denselben Wert, und ihre Reihenfolge hing von der Plattform ab, etwa von den Rundungen der CPU-Befehle. Jetzt wird auf 6 Nachkommastellen gerundet und bei Gleichstand nach der Position des Abschnitts sortiert. In einem Linux-Container (amd64) kommen exakt dieselben Zahlen heraus wie auf dem Mac (arm64). Die vorher veröffentlichten Zahlen waren um einige Hundertstel zu günstig und sind korrigiert.

## Welche Alternativen gab es?

| Entscheidung | Gewählt | Alternative | Warum so |
|---|---|---|---|
| Embedding-Backend | Ollama | sentence-transformers direkt | Ollama läuft ohnehin für das Sprachmodell, nutzt die Mac-GPU und braucht keine zweite Modellverwaltung. sentence-transformers bleibt als Option. |
| Modell | qwen3-embedding:0.6b | bge-m3 | Gemessen besser (MRR 0,98 gegen 0,92) und kleiner. bge-m3 hat zusätzlich „sparse“ Vektoren, die nutzen wir aber nicht. |
| Vektordatenbank | FAISS-Datei + Manifest | Qdrant, pgvector, Chroma | 76 Abschnitte brauchen keinen Server. Ein Server lohnt sich bei vielen Dokumenten, häufigen Änderungen oder mehreren Instanzen. |
| Reranker | noch keiner | Cross-Encoder wie bge-reranker-v2-m3 | Die Messung zeigt Recall 1,0 ohne Reranker. Ein Reranker ist der nächste Schritt, wenn die Wissensbasis wächst. |
| Router | Regeln + Beispiel-Embeddings | Sprachmodell als Router | Schneller (8 ms statt Sekunden), deterministisch und testbar. |

## Was ist bewusst noch offen?

- Die Testsätze sind klein und stammen von mir. Ein Unterschied von 0,1 entspricht zwei Fragen.
- Der Abschnitt „Dokumentenlenkung“ (Verantwortliche, Prüfzyklus) taucht manchmal unter den Treffern auf. Er beantwortet „Wer ist verantwortlich?“, stört aber bei Sachfragen.
- Die Antwortqualität des Sprachmodells (siehe Halluzination in Paket 1) wird erst in Paket 4 gemessen.

## Fragen im Vorstellungsgespräch

**„Warum nicht einfach das beste Modell aus einem Leaderboard nehmen?“**
Leaderboards messen allgemeine Texte. Unsere Texte sind deutsche Bankrichtlinien mit Fachwörtern und Komposita. Eine Messung auf den eigenen Daten dauert eine Stunde und schützt vor Fehlentscheidungen. Bei uns lag ein kleines Modell (0,6B) vor größeren.

**„Was ist der Unterschied zwischen Recall@5 und MRR?“**
Recall@5 fragt: Ist die richtige Quelle irgendwo unter den ersten fünf Treffern? MRR fragt: Wie weit oben? Platz 1 zählt 1, Platz 2 zählt 0,5 und so weiter. Für ein Sprachmodell ist MRR wichtig, weil es den ersten Treffern am meisten Gewicht gibt.

**„Wie verhindert ihr, dass RAG Antworten auf Fragen erfindet, die die Wissensbasis nicht abdeckt?“**
Mit einer Schwelle für die Ähnlichkeit. Liegt der beste Treffer darunter, sagt die Suche „keine Antwort“, und das Modell bekommt keinen Text. Die Schwelle ist pro Modell kalibriert, auf getrennten Daten.

**„Warum filtert ihr vor dem Ranking? Nachher filtern ist doch einfacher.“**
Weil sonst verbotene Dokumente die Ergebnisse beeinflussen. Ein Angreifer könnte durch geschickte Fragen herausfinden, ob es ein Dokument zu einem Thema gibt. Unser Test hat genau so einen Effekt bei BM25 gefunden.

**„Warum hat eure CI andere Zahlen gemessen als dein Laptop?“**
Weil die Reihenfolge bei gleichen Werten nicht festgelegt war. Gleitkommazahlen werden auf ARM und x86 minimal anders gerundet, und Bibliotheken sortieren Gleichstände unterschiedlich. Die Lösung: gerundet vergleichen und Gleichstände nach einer festen Regel auflösen. Geprüft habe ich das, indem ich die Evaluation in einem Linux-Container wiederholt habe.

**„Warum ist der Index persistent und was steht im Manifest?“**
Embeddings zu berechnen kostet Zeit, in unserem Fall 2 Sekunden, bei großen Wissensbasen Stunden. Das Manifest stellt sicher, dass Modell, Wissensbasis und Zerlegung zum Index passen. Sonst würde man Vektoren eines alten Modells mit Fragen eines neuen vergleichen, und das ergibt Unsinn ohne Fehlermeldung.

**„Warum braucht man bei manchen Embedding-Modellen Vorsätze wie ‚Instruct:‘?“**
Diese Modelle sind asymmetrisch trainiert: Fragen und Dokumente werden unterschiedlich kodiert. Fehlen die Vorsätze, sinkt die Qualität messbar. Das steht in der Modellkarte und wird leicht übersehen.
