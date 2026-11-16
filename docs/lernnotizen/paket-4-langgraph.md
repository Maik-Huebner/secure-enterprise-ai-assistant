# Lernnotiz Paket 4 – LangGraph statt CrewAI, Antwortprüfung und Freigabe (v1.4)

## Worum ging es?

In v1.3 lief der Assistent über CrewAI. Dort entscheidet das Sprachmodell selbst, welche Werkzeuge es aufruft, und wann es fertig ist. Das hatte drei Probleme:

1. **Zu viel Freiheit für das Modell.** Ein eingeschleuster Text in einem Dokument hätte einen Werkzeugaufruf auslösen können.
2. **Keine Prüfung der Antwort.** In Paket 1 hat das Modell bei einer Wissensfrage zwei Unterlagen frei erfunden, und niemand hat es bemerkt.
3. **Keine echte Freigabe.** Eine Entscheidungsvorlage war einfach fertig. Es gab keinen Schritt, in dem eine zweite Person zustimmen muss.

Dazu kam: CrewAI brachte über 100 Pakete mit, darunter `chromadb` mit einer bekannten Sicherheitslücke.

## Was wurde gebaut?

### 1. Ein Graph statt einer Crew

LangGraph beschreibt den Ablauf als **Graph aus Knoten und Kanten**. Jeder Knoten ist eine normale Python-Funktion. Die Kanten legen fest, was danach kommt.

```
receive → route → collect_evidence → generate → verify → finish
                                   ↘              ↓ Mängel
                                    draft_brief   generate (2. Versuch) → verify → fallback
                                      ↓
                                    human_review ⏸ → check_review → Ende
```

- **route:** Fall-ID-Regel und hybrider Router aus Paket 2. Er legt den **Werkzeugplan** fest.
- **collect_evidence:** ruft genau diese Werkzeuge über MCP auf, mit dem Token der angemeldeten Person.
- **generate:** das Sprachmodell (`qwen3.5:9b`) formuliert eine Antwort **nur aus den Nachweisen**.
- **verify:** prüft die Antwort im Code (siehe unten).
- **fallback:** Wenn auch der zweite Versuch durchfällt, baut der Code die Antwort aus den strukturierten Daten, ganz ohne Modell.

### 2. „Least Agency“ – das Modell wählt keine Werkzeuge

Das ist die wichtigste Entscheidung. Das Modell bekommt nur Text und gibt Text zurück. Welche Werkzeuge laufen, steht vorher fest. Ein Angreifer kann also mit einem präparierten Dokument keinen Werkzeugaufruf erzwingen. Der Fachbegriff aus den OWASP-Top-10 für LLM-Anwendungen heißt „Excessive Agency“ (zu viel Handlungsfreiheit). Hier ist sie bewusst klein.

### 3. Antwortprüfung im Code

Eine Antwort fällt durch, wenn

- eine **Zahl** darin steht, die nicht in den Nachweisen vorkommt (deutsche und englische Schreibweise werden beide erkannt; kleine Zähler bis 12 werden ignoriert),
- eine **Dokument-ID** zitiert wird, die nicht gefunden wurde, oder ein Platzhalter wie `NB-DOC-XXX`,
- bei Richtlinienaussagen **keine Quelle** genannt wird,
- **englische Beschriftungen** wie „Monthly Payment“ vorkommen.

Beim ersten Durchfallen bekommt das Modell die Mängelliste und einen zweiten Versuch. Danach greift der Rückfallweg.

### 4. Freigabe mit Vier-Augen-Prinzip

Eine Entscheidungsvorlage schreibt **kein Modell**. Der Code baut sie aus den MCP-Daten. Dann hält der Graph mit `interrupt()` an. Der Zustand liegt in einer SQLite-Datenbank (Checkpointer), die Pause übersteht also einen Neustart der API.

Freigeben oder ablehnen darf nur eine **andere** prüfende Person (`POST /v1/reviews/{id}`). Versucht die Autorin selbst freizugeben, wird das in einem eigenen Knoten (`check_review`) abgewiesen, und der Graph pausiert erneut. Die abgewiesene Entscheidung kann so nie später „nachrutschen“. Auch der abgewiesene Versuch steht im Protokoll.

### 5. Das Token landet nicht in der Datenbank

Name, Rolle und Token werden dem Graphen als **Laufzeit-Kontext** übergeben (`context_schema`), nicht als Zustand. Der Checkpointer speichert nur den Zustand. Ein Test sucht das Token in der SQLite-Datei und findet es nicht.

### 6. Empfehlung aus Regeln

Der neue `DecisionService` leitet die Empfehlung aus dem Regelwerk ab: Eine kritische Regel mit `hard_decline` (KYC abgelehnt, DTI über 50 %, Risikoklasse außerhalb) → „Ablehnung“; offene Warnungen oder fehlende Unterlagen → „Manuelle Prüfung“; sonst „Genehmigungskandidat“. Die Entscheidung trifft immer ein Mensch.

## Was ich beim Bauen gefunden habe

- **Selbstfreigabe rutschte durch.** In der ersten Version blieb ein abgewiesener Freigabewert im Zustand hängen und wurde beim nächsten Fortsetzen übernommen. Lösung: eigener Prüfknoten mit Schleife zurück zur Pause.
- **Querverweise wurden als Fehler gemeldet.** Eine Richtlinie verweist auf `NB-ESC-001`. Das Modell zitierte das korrekt, die Prüfung meldete es aber als „nicht gefunden“. Jetzt gilt: Zitierbar ist, was gefunden wurde, und was in den gefundenen Texten genannt wird.
- **Compliance-Antworten hatten die falsche Quelle.** Die Suche fand allgemeine Texte, aber nicht das Dokument, auf das sich die verletzte Regel stützt. Jetzt sucht der Werkzeug-Knoten zuerst in den Quelldokumenten der verletzten Regeln.
- **Das Modell rechnet trotz Verbot.** Bei „Berechne die finanzielle Belastung“ addierte es bestehende Verpflichtungen und neue Rate (980,00 + 570,64 = 1.550,64 EUR). Die Rechnung stimmte sogar, die Prüfung hat sie trotzdem zu Recht abgelehnt: Zahlen kommen aus dem Code. Lösung: Der Finanzrechner liefert diese Summe und den Anstieg der DTI in Prozentpunkten jetzt selbst mit.
- **Das Beispiel im Prompt wurde zitiert.** Im Systemprompt stand als Beispiel „(NB-DOC-001, Abschnitt 3.1)“. Bei einer Finanzfrage ohne Richtlinien hat das Modell genau diese ID erwähnt. Das Beispiel ist jetzt neutral.

## Messung der Antwortqualität

Das Skript `scripts/evaluate_answers.py` stellt 17 Fragen an den echten Ablauf (Graph, MCP, `qwen3.5:9b`). Gemessen wird:

- **Fakten:** Stehen die erwarteten Fakten in der Antwort? (Wortvergleich mit erlaubten Schreibweisen)
- **Quellen:** Werden nur gefundene Dokumente zitiert, und das erwartete Dokument?
- **Richter:** Dasselbe 9B-Modell bewertet, ob jede Aussage belegt ist.
- **Vergleich ohne RAG:** dasselbe Modell, dieselbe Frage, ohne Nachweise.
- **Handprüfung:** Ich habe jede Modellantwort selbst gelesen, mit strenger Regel: Auch eine kleine Schlussfolgerung, die so nicht dasteht, zählt als unbelegt.

| | Lauf 1 | Lauf 2 | Lauf 3 (v1.4) |
|---|---:|---:|---:|
| alle erwarteten Fakten | 14/15 | 13/15 | 13/15 |
| ohne Antwort richtig abgelehnt | 2/2 | 2/2 | 2/2 |
| nur gefundene Quellen zitiert | 11/12 | 12/12 | 12/12 |
| Rückfallweg ohne Modell | 2/15 | 1/15 | 0/15 |
| Richter: belegt | 0,92 | 1,00 | 0,93 |
| **Handprüfung: belegt** | **8/11** | **9/13** | **11/14** |
| Wissensfragen mit RAG / ohne RAG | 9/10 / 1/10 | 8/10 / 1/10 | 8/10 / 1/10 |
| Median pro Frage | 11,6 s | 11,1 s | 9,2 s |

**Was ich daraus gelernt habe:**

1. **Der Richter ist zu nett.** In Lauf 2 hat er alles als belegt bewertet, ich fand 4 von 13 Antworten teilweise unbelegt. Ein Modell, das seine eigenen Antworten bewertet, übersieht seine eigenen Fehler. Deshalb steht die Handprüfung daneben.
2. **Die Läufe sind nicht unabhängig.** Nach jedem Lauf habe ich Fehler behoben, die genau diese Fragen gezeigt haben. Lauf 3 ist deshalb zu optimistisch. Ehrlich wäre ein zweiter Fragenkatalog, den ich vorher nicht kenne.
3. **Die Prüfung im Code fängt Zahlen und IDs, aber keine falschen Wörter.** „Berufserfahrung“ statt „Beschäftigungsdauer“ oder eine erfundene „bestehende Warnung“ rutschen durch. Auch eine falsche, aber gefundene Quelle erkennt sie nicht.
4. **„Keine Antwort“ ist manchmal falsch, aber sicher.** Die Frage „Was darf in Protokollen nicht stehen?“ wird abgelehnt, weil die Suche `NB-DPR-001` nicht weit genug oben findet. Ich habe das bewusst nicht an der Schwelle hingedreht. Ein Reranker ist der richtige nächste Schritt.
5. **RAG macht hier den Unterschied:** Ohne Nachweise beantwortet das Modell nur 1 von 10 Fragen richtig. Die Richtlinien sind erfunden, das Modell kann sie nicht kennen.

## Welche Alternativen gab es?

| Entscheidung | Gewählt | Alternative | Warum so |
|---|---|---|---|
| Orchestrierung | LangGraph 1.2 | CrewAI behalten, OpenAI Agents SDK, eigener Code | LangGraph bietet Checkpointer, `interrupt` und feste Kanten. Genau das braucht ein prüfbarer Bankablauf. |
| Werkzeugwahl | Router legt fest | Modell wählt per Tool Calling | Ein 9B-Modell wählt nicht zuverlässig, und jede Wahlfreiheit ist Angriffsfläche. |
| MCP-Anbindung | eigener kleiner Client | `langchain-mcp-adapters` | Der Adapter macht MCP-Werkzeuge zu Werkzeugen, die das Modell wählt. Das wollen wir gerade nicht. Außerdem verlangt er `mcp<2` und hätte Paket 5 blockiert. |
| Freigabe | `interrupt` + SQLite | eigene Statustabelle | Der Entwurf und der Ablauf liegen am selben Ort; Fortsetzen ist eine Zeile. |
| Antwortprüfung | Regeln im Code | zweites Modell als Prüfer | Regeln sind schnell, erklärbar und nicht überredbar. Ein Prüfmodell nutze ich nur in der Evaluation. |
| Rückfallweg | Antwort aus Daten | Fehlermeldung | Die Person bekommt korrekte Fakten statt nichts; der Modus wird offen angezeigt. |

## Fragen im Vorstellungsgespräch

**„Warum LangGraph und nicht einfach ein Agent mit Tool Calling?“**
Weil der Ablauf in einer Bank vorhersehbar und prüfbar sein muss. Im Graphen sehe ich jeden Schritt, kann ihn testen und kann an festen Stellen anhalten. Ein freier Agent entscheidet selbst, was er tut, und das ist bei einem kleinen lokalen Modell weder zuverlässig noch sicher.

**„Wie verhindert ihr Halluzinationen?“**
Verhindern kann man sie nicht ganz. Wir begrenzen sie: Das Modell bekommt nur Nachweise, die Antwort wird im Code gegen diese Nachweise geprüft, und bei zwei Fehlversuchen kommt die Antwort aus den Daten. Die Messung zeigt aber auch, was die Prüfung nicht sieht: falsche Wörter ohne Zahl und ohne ID, etwa „Berufserfahrung“ statt „Beschäftigungsdauer“.

**„Was ist ein Checkpointer?“**
Er speichert den Zustand des Graphen nach jedem Schritt. Damit kann ein Ablauf anhalten, zum Beispiel für eine Freigabe, und Stunden später an derselben Stelle weiterlaufen, auch nach einem Neustart.

**„Wie testet ihr einen Ablauf mit Sprachmodell, ohne dass die Tests zufällig sind?“**
Die Tests ersetzen das Modell durch kleine Testmodelle: eines antwortet korrekt mit Quelle, eines erfindet Zahlen. So prüfen die Tests den Graphen, die Prüfung und den Rückfallweg, ohne Ollama. Das echte Modell wird getrennt mit einem eigenen Skript gemessen.

**„Warum ist euer LLM-Richter schwach?“**
Er ist dasselbe 9B-Modell, das die Antworten schreibt. Er hat in beiden Läufen fast alles als belegt bewertet, auch Antworten, die ich von Hand als teilweise unbelegt eingestuft habe. Deshalb steht die Handprüfung neben der Richter-Zahl. Ein stärkerer, unabhängiger Richter wäre der nächste Schritt.
