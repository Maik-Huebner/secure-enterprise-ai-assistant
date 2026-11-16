// Erzeugt output/presentation/10_Minuten_Praesentation_Secure_Enterprise_AI_Assistant_FINAL.pptx.
// Sprechernotizen kommen aus docs/presentation-speaker-notes.md, Zahlen aus README und reports/.
// Aufruf: npm install && node praesentation.cjs   (siehe tools/dokumente/README.md)

const fs = require("node:fs");
const path = require("node:path");
const PptxGenJS = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..", "..");
const ASSETS = path.join(ROOT, "docs", "assets");
const OUT = path.join(ROOT, "output", "presentation",
  "10_Minuten_Praesentation_Secure_Enterprise_AI_Assistant_FINAL.pptx");

const C = {
  navy: "13294B", slate: "3E5470", teal: "0E7C86", tealLight: "9AD3D6", tealTint: "E3F4F4",
  tint: "EEF3F9", line: "C9D6E6", orange: "C46A0A", orangeTint: "FFF4E5", grey: "6B7C93",
  white: "FFFFFF",
};
// Georgia gibt es unter Windows, macOS und in Office; Keynote rendert sie für das PDF exakt.
const HEAD = "Georgia";
const BODY = "Calibri";
// Große Kennzahlen in Calibri: Georgia hat Mediävalziffern, die als Zahl unruhig wirken.
const NUMBER = BODY;
const W = 13.333;

// ---------- Sprechernotizen ----------
const notesText = fs.readFileSync(path.join(ROOT, "docs", "presentation-speaker-notes.md"), "utf8");
const notes = notesText.split(/^## Folie \d+: .*$/m).slice(1).map((block) =>
  block.trim().replace(/\*\*Zielzeit:\*\*/, "Zielzeit:").replace(/\n{3,}/g, "\n\n"));
if (notes.length !== 10) throw new Error(`10 Notizblöcke erwartet, gefunden: ${notes.length}`);

const pres = new PptxGenJS();
pres.layout = "LAYOUT_WIDE";
pres.author = "Secure Enterprise AI Assistant";
pres.company = "NovaBank Financial Services AG (fiktiv)";
pres.title = "Secure Enterprise AI Assistant – 10-Minuten-Präsentation (v2.1)";
pres.subject = "Lokale, nachprüfbare Entscheidungsunterstützung für synthetische Kreditfälle";
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };

pres.defineSlideMaster({
  title: "DUNKEL",
  background: { color: C.navy },
  objects: [],
});
pres.defineSlideMaster({
  title: "INHALT",
  background: { color: C.white },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 11.4, h: 0.85,
      fontFace: HEAD, fontSize: 30, bold: true, color: C.navy, valign: "middle", align: "left",
      margin: 0 },
      text: "" } },
    { text: { text: "Secure Enterprise AI Assistant · v2.1 · NovaBank ist fiktiv, alle Daten synthetisch",
      options: { x: 0.6, y: 7.0, w: 9.5, h: 0.3, fontFace: BODY, fontSize: 10, color: C.grey,
        margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontFace: BODY, fontSize: 10, color: C.grey,
    align: "right" },
});

function slide(master, section, title) {
  if (section) pres.addSection({ title: section });
  const s = pres.addSlide({ masterName: master, sectionTitle: section || currentSection });
  if (section) currentSection = section;
  if (title) s.addText(title, { placeholder: "title", align: "left", bold: true });
  return s;
}
let currentSection = "";

function text(s, value, opts) {
  s.addText(value, { fontFace: BODY, color: C.slate, fontSize: 16, margin: 0, isTextBox: true,
    valign: "top", ...opts });
}
function card(s, x, y, w, h, fill, line, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12,
    fill: { color: fill }, line: { color: line || fill, width: 1 }, objectName: name });
}
function badge(s, x, y, label, fill, color) {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.5, h: 0.5, fill: { color: fill || C.teal },
    line: { color: fill || C.teal } });
  s.addText(label, { x, y, w: 0.5, h: 0.5, align: "center", valign: "middle", fontFace: BODY,
    fontSize: 16, bold: true, color: color || C.white, margin: 0, isTextBox: true });
}
function image(s, file, x, y, w, h, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.08, y: y - 0.08, w: w + 0.16, h: h + 0.16,
    rectRadius: 0.1, fill: { color: C.white }, line: { color: C.line, width: 1 },
    shadow: { type: "outer", color: "000000", opacity: 0.18, blur: 8, offset: 3, angle: 90 } });
  s.addImage({ path: path.join(ASSETS, file), x, y, w, h, altText: name });
}

// ---------- Folie 1 ----------
{
  const s = slide("DUNKEL", "Einstieg");
  text(s, "Secure Enterprise\nAI Assistant", { x: 0.7, y: 1.3, w: 6.0, h: 1.9, fontFace: HEAD,
    fontSize: 36, bold: true, color: C.white });
  text(s, "Lokale, nachprüfbare Entscheidungsunterstützung für Kreditfälle",
    { x: 0.7, y: 3.35, w: 5.4, h: 0.9, fontSize: 20, color: "DCE8F5" });
  text(s, "NovaBank Financial Services AG – fiktiv, alle Daten synthetisch",
    { x: 0.7, y: 4.45, w: 5.4, h: 0.7, fontSize: 16, bold: true, color: C.tealLight });
  text(s, "Release v2.1.0 · MacBook Pro M4 Pro · qwen3.5:9b über Ollama",
    { x: 0.7, y: 5.9, w: 5.6, h: 0.4, fontSize: 14, color: "B8C7DA" });
  image(s, "ui-v2-assistant.jpg", 6.75, 1.55, 6.0, 4.16, "Assistent mit geprüfter Finanzantwort");
  s.addNotes(notes[0]);
}

// ---------- Folie 2 ----------
{
  const s = slide("INHALT", "Problem und Ansatz", "Fakten aus Code, Sprache aus dem Modell");
  card(s, 0.6, 1.5, 5.75, 4.65, C.orangeTint, "F0C98A", "Risiken");
  text(s, "Ein reiner Chatbot …", { x: 0.95, y: 1.75, w: 5.1, h: 0.5, fontFace: HEAD,
    fontSize: 22, bold: true, color: C.orange });
  const risks = [
    ["verrechnet sich", "Raten und Quoten klingen richtig, sind es aber nicht immer."],
    ["übersieht Regeln", "Eine fehlende Unterlage fällt nicht auf."],
    ["erfindet Quellen", "Richtlinie und Abschnitt passen nicht zum Inhalt."],
  ];
  risks.forEach(([head, body], i) => {
    const y = 2.5 + i * 1.18;
    badge(s, 0.95, y, "!", C.orange);
    text(s, [{ text: head, options: { bold: true, color: C.navy, breakLine: true } },
      { text: body }], { x: 1.65, y: y - 0.05, w: 4.45, h: 1.0, fontSize: 16 });
  });
  card(s, 6.95, 1.5, 5.75, 4.65, C.tealTint, C.tealLight, "Ansatz");
  text(s, "… dieses Projekt", { x: 7.3, y: 1.75, w: 5.1, h: 0.5, fontFace: HEAD, fontSize: 22,
    bold: true, color: C.teal });
  const answers = [
    ["Rechner und Regelwerk hinter MCP", "Decimal-genau, zehn Regeln mit Quelle"],
    ["Quellenpflicht", "jede Richtlinienaussage mit Dokument und Abschnitt"],
    ["automatische Antwortprüfung", "Zahlen und IDs müssen in den Nachweisen stehen"],
    ["Freigabe durch einen Menschen", "Vier-Augen-Prinzip für jede Vorlage"],
  ];
  answers.forEach(([head, body], i) => {
    const y = 2.45 + i * 0.9;
    badge(s, 7.3, y, String(i + 1));
    text(s, [{ text: head, options: { bold: true, color: C.navy, breakLine: true } },
      { text: body }], { x: 8.0, y: y - 0.05, w: 4.5, h: 0.85, fontSize: 15 });
  });
  text(s, "Ziel: ein prüfbarer Assistent – kein autonomer Kreditentscheider",
    { x: 0.6, y: 6.35, w: 12.1, h: 0.45, fontSize: 17, italic: true, color: C.navy,
      align: "center" });
  s.addNotes(notes[1]);
}

// ---------- Folie 3 ----------
{
  const s = slide("INHALT", null, "Von v1 zu v2: gemessen, nicht behauptet");
  const stats = [
    ["1,00", "Recall@5 im Testteil", "v1: 0,75 mit Hashing"],
    ["15/20", "Angriffe erkannt (Holdout)", "v1: 1 von 12"],
    ["9B", "ein lokales Modell, LangGraph", "v1: CrewAI mit 24B über der Hardware-Grenze"],
    ["3 Rollen", "Anmeldung, Rechte, Protokoll", "v1: keine Anmeldung, kein Audit-Log"],
  ];
  stats.forEach(([big, label, before], i) => {
    const x = 0.6 + i * 3.08;
    card(s, x, 1.45, 2.85, 2.85, C.tint, C.line, `Kennzahl ${i + 1}`);
    text(s, big, { x: x + 0.25, y: 1.65, w: 2.4, h: 0.95, fontFace: NUMBER, fontSize: 40,
      bold: true, color: C.teal });
    text(s, label, { x: x + 0.25, y: 2.65, w: 2.4, h: 0.7, fontSize: 16, bold: true,
      color: C.navy });
    text(s, before, { x: x + 0.25, y: 3.4, w: 2.4, h: 0.75, fontSize: 13, color: C.grey });
  });
  text(s, "Neun Pakete – jedes mit Branch, Pull Request, Tag und Lernnotiz",
    { x: 0.6, y: 4.6, w: 12.1, h: 0.4, fontSize: 17, bold: true, color: C.navy });
  const steps = ["Fundament", "Deutsch", "Suche", "API", "LangGraph", "MCP-HTTP", "Langfuse",
    "Release 2.0", "Deutsch komplett"];
  const step = 12.1 / steps.length;
  s.addShape(pres.shapes.LINE, { x: 0.6 + step / 2, y: 5.5, w: step * (steps.length - 1), h: 0,
    line: { color: C.line, width: 2 } });
  steps.forEach((label, i) => {
    const cx = 0.6 + step * i + step / 2;
    badge(s, cx - 0.25, 5.25, String(i), i === steps.length - 1 ? C.navy : C.teal);
    text(s, label, { x: cx - step / 2, y: 5.85, w: step, h: 0.6, fontSize: 12, align: "center",
      color: C.slate });
  });
  s.addNotes(notes[2]);
}

// ---------- Folie 4 ----------
{
  const s = slide("INHALT", "Architektur", "Architektur: Das Modell wählt keine Werkzeuge");
  s.addImage({ path: path.join(ASSETS, "architektur-v2.png"), x: 1.7, y: 1.3, w: 9.95, h: 5.6,
    altText: "Architektur: Zugang, LangGraph-Workflow, MCP-Server" });
  s.addNotes(notes[3]);
}

// ---------- Folie 5 ----------
{
  const s = slide("INHALT", null, "Suche und Routing: gemessen und rechtebewusst");
  // Balken als Formen: Keynote (PDF-Export) zeigt pptxgenjs-Diagramme nicht an.
  text(s, "MRR im Testteil (20 Fragen, gemessen am 16.11.2026)", { x: 0.6, y: 1.4, w: 6.4,
    h: 0.4, fontSize: 15, bold: true, color: C.navy });
  // Werte aus reports/evaluation/retrieval_comparison.json, Anzeige wie im README gerundet.
  const bars = [["Hashing (v1)", 0.604, "0,60"], ["bge-m3", 0.917, "0,92"],
    ["qwen3-embedding\n0.6b", 0.975, "0,98"], ["embedding-\ngemma", 0.9, "0,90"]];
  const base = 5.75;
  const maxH = 3.3;
  s.addShape(pres.shapes.LINE, { x: 0.6, y: base, w: 6.4, h: 0, line: { color: C.line, width: 1.5 } });
  bars.forEach(([label, value, shown], i) => {
    const x = 0.85 + i * 1.55;
    const h = maxH * value;
    const best = i === 2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: base - h, w: 1.05, h,
      fill: { color: best ? C.teal : "7A93B5" }, line: { color: best ? C.teal : "7A93B5" },
      objectName: `Balken ${label}` });
    text(s, shown, { x: x - 0.2, y: base - h - 0.5, w: 1.45, h: 0.45,
      fontSize: 16, bold: true, align: "center", color: best ? C.teal : C.navy,
      fontFace: NUMBER });
    text(s, label, { x: x - 0.25, y: base + 0.1, w: 1.55, h: 0.6, fontSize: 12, align: "center",
      color: C.slate });
  });
  const points = [
    ["Drei Signale", "Vektoren (FAISS), Wortsuche (BM25), Dokument- und Abschnittskennungen"],
    ["Filter vor dem Ranking", "vertrauliche Dokumente beeinflussen das Ergebnis nicht"],
    ["„Keine Antwort“ statt Raten", "unter der Schwelle wird das Modell gar nicht gefragt"],
  ];
  points.forEach(([head, body], i) => {
    const y = 1.55 + i * 1.12;
    badge(s, 7.4, y, String(i + 1));
    text(s, [{ text: head, options: { bold: true, color: C.navy, breakLine: true } },
      { text: body }], { x: 8.1, y: y - 0.05, w: 4.6, h: 1.0, fontSize: 15 });
  });
  card(s, 7.4, 5.05, 5.3, 1.2, C.navy, C.navy, "Router");
  text(s, "24/24", { x: 7.7, y: 5.25, w: 1.9, h: 0.8, fontFace: NUMBER, fontSize: 36, bold: true,
    color: C.white });
  text(s, "Router im Testteil richtig\n8 ms, ohne Sprachmodell",
    { x: 9.6, y: 5.3, w: 3.0, h: 0.75, fontSize: 15, color: "DCE8F5", valign: "middle" });
  s.addNotes(notes[4]);
}

// ---------- Folie 6 ----------
{
  const s = slide("INHALT", "Ablauf und Beispiel", "Antwortprüfung und Vier-Augen-Freigabe");
  text(s, "Jede Antwort", { x: 0.6, y: 1.4, w: 5.8, h: 0.45, fontFace: HEAD, fontSize: 20,
    bold: true, color: C.teal });
  const answerSteps = [
    "Modell formuliert nur aus den Nachweisen",
    "Prüfung: Zahlen, IDs, Quellen, deutsche Begriffe",
    "Mängel → zweiter Versuch mit Mängelliste",
    "danach: Antwort aus den Daten, ohne Modell",
  ];
  answerSteps.forEach((label, i) => {
    const y = 1.95 + i * 0.62;
    badge(s, 0.6, y, String(i + 1));
    text(s, label, { x: 1.3, y, w: 5.2, h: 0.5, fontSize: 16, valign: "middle" });
  });
  text(s, "Jede Entscheidungsvorlage", { x: 0.6, y: 4.6, w: 5.8, h: 0.45, fontFace: HEAD,
    fontSize: 20, bold: true, color: C.navy });
  const briefSteps = ["ohne Modell", "Pause", "zweite Person"];
  briefSteps.forEach((label, i) => {
    const x = 0.6 + i * 1.95;
    card(s, x, 5.15, 1.75, 0.75, i === 2 ? C.navy : C.tint, i === 2 ? C.navy : C.line,
      `Vorlage ${i + 1}`);
    text(s, label, { x, y: 5.15, w: 1.75, h: 0.75, fontSize: 15, bold: true, align: "center",
      valign: "middle", color: i === 2 ? C.white : C.navy });
  });
  text(s, "Selbstfreigabe wird abgewiesen und protokolliert.",
    { x: 0.6, y: 6.1, w: 5.8, h: 0.4, fontSize: 14, italic: true, color: C.grey });
  image(s, "ui-v2-approval.jpg", 6.95, 1.55, 5.75, 3.99, "Freigabe durch eine zweite Person");
  text(s, "Reiter „Freigaben“: Nur eine zweite prüfende Person kann freigeben oder ablehnen.",
    { x: 6.95, y: 5.8, w: 5.75, h: 0.6, fontSize: 13, color: C.grey });
  s.addNotes(notes[5]);
}

// ---------- Folie 7 ----------
{
  const s = slide("INHALT", null, "Praxisbeispiel CASE-00031 (synthetisch)");
  const stats = [
    ["570,64 EUR", "monatliche Rate"],
    ["44,95 %", "DTI nach Kredit (vorher 28,41 %)"],
    ["5.488,40 EUR", "Gesamtzins über 60 Monate"],
  ];
  stats.forEach(([big, label], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.4, 3.85, 1.7, C.tint, C.line, `Kennzahl ${i + 1}`);
    text(s, big, { x: x + 0.25, y: 1.55, w: 3.4, h: 0.8, fontFace: NUMBER, fontSize: 34,
      bold: true, color: i === 1 ? C.orange : C.navy });
    text(s, label, { x: x + 0.25, y: 2.4, w: 3.4, h: 0.5, fontSize: 15 });
  });
  text(s, "Regelwerk: 9 von 10 Regeln bestanden", { x: 0.6, y: 3.4, w: 12, h: 0.45,
    fontFace: HEAD, fontSize: 20, bold: true, color: C.navy });
  for (let i = 1; i <= 10; i += 1) {
    const failed = i === 5;
    const x = 0.6 + (i - 1) * 1.23;
    card(s, x, 3.95, 1.1, 0.8, failed ? C.orangeTint : C.tealTint, failed ? "F0C98A" : C.tealLight,
      `Regel ${i}`);
    text(s, [{ text: `RULE-${String(i).padStart(3, "0")}`, options: { breakLine: true } },
      { text: failed ? "✗" : "✓", options: { bold: true, fontSize: 16 } }],
      { x, y: 3.98, w: 1.1, h: 0.75, fontSize: 11, align: "center", valign: "middle",
        color: failed ? C.orange : C.teal });
  }
  text(s, "RULE-005: DTI über der Prüfschwelle von 40 % → Empfehlung „Manuelle Prüfung“",
    { x: 0.6, y: 4.9, w: 12.1, h: 0.45, fontSize: 16, bold: true, color: C.orange });
  const flow = ["Vorlage ohne Modell", "Selbstfreigabe abgewiesen", "Freigabe durch zweite Person"];
  flow.forEach((label, i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 5.6, 3.85, 0.85, i === 2 ? C.navy : C.white, i === 2 ? C.navy : C.line,
      `Ablauf ${i + 1}`);
    text(s, label, { x, y: 5.6, w: 3.85, h: 0.85, fontSize: 16, bold: true, align: "center",
      valign: "middle", color: i === 2 ? C.white : C.navy });
    if (i < 2) {
      s.addShape(pres.shapes.LINE, { x: x + 3.88, y: 6.025, w: 0.19, h: 0,
        line: { color: C.slate, width: 2, endArrowType: "triangle" } });
    }
  });
  s.addNotes(notes[6]);
}

// ---------- Folie 8 ----------
{
  const s = slide("INHALT", "Sicherheit und Qualität", "Sicherheit: Rechte im Code, nicht im Prompt");
  const items = [
    ["Rollen und Team-Rechte", "Sachbearbeitung sieht nur das eigene Team; fremde Fälle wie unbekannte (404)"],
    ["Eigenes MCP-Token", "pro Lauf, 5 Minuten, Audience novabank-mcp – kein Token Passthrough"],
    ["Eingabefilter", "Deutsch und Englisch, 15 von 20 Angriffen im Holdout – nur eine Schicht"],
    ["Dokumente sind Daten", "markiert im Prompt, Quarantäne bei Injektionsmustern"],
    ["Audit-Log", "SHA-256-Hash-Kette, ohne Passwörter und Fragetexte"],
    ["Alles lokal", "Ollama auf dem Mac, Ports nur an 127.0.0.1, Langfuse selbst gehostet"],
  ];
  items.forEach(([head, body], i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.6 + col * 4.1;
    const y = 1.6 + row * 2.55;
    card(s, x, y, 3.85, 2.2, row === 0 ? C.tint : C.white, C.line, head);
    badge(s, x + 0.25, y + 0.25, String(i + 1), row === 0 ? C.navy : C.teal);
    text(s, head, { x: x + 0.9, y: y + 0.27, w: 2.8, h: 0.5, fontSize: 17, bold: true,
      color: C.navy });
    text(s, body, { x: x + 0.25, y: y + 0.95, w: 3.4, h: 1.3, fontSize: 15 });
  });
  s.addNotes(notes[7]);
}

// ---------- Folie 9 ----------
{
  const s = slide("INHALT", null, "Qualität ehrlich gemessen");
  const rows = [
    ["Kennzahl (Lauf 3, qwen3.5:9b, 17 Fragen)", "Ergebnis"],
    ["alle erwarteten Fakten", "13/15"],
    ["Fragen ohne Antwort richtig abgelehnt", "2/2"],
    ["nur gefundene Dokumente zitiert", "12/12"],
    ["Endantworten mit offenen Prüfmängeln", "0"],
    ["Handprüfung: vollständig belegt", "11/14"],
    ["Median pro Frage", "9,2 s"],
  ].map((row, r) => row.map((value, c) => ({
    text: value,
    options: {
      bold: r === 0 || c === 1, color: r === 0 ? C.white : C.navy,
      fill: { color: r === 0 ? C.navy : (r % 2 ? C.white : C.tint) },
      align: c === 1 ? "right" : "left", valign: "middle", fontFace: BODY, fontSize: 15,
    },
  })));
  s.addTable(rows, { x: 0.6, y: 1.45, w: 7.0, colW: [5.4, 1.6], rowH: 0.55,
    border: { type: "solid", color: C.line, pt: 1 }, margin: [0.05, 0.12, 0.05, 0.12] });
  const callouts = [
    ["8/10 · 1/10", "Richtlinienfragen richtig mit Suche · ohne Suche (gleiches Modell)"],
    ["321 + 4", "automatisierte Tests + Live-Tests mit echtem Modell"],
  ];
  callouts.forEach(([big, label], i) => {
    const y = 1.45 + i * 1.95;
    card(s, 8.1, y, 4.6, 1.75, i === 0 ? C.tealTint : C.tint, i === 0 ? C.tealLight : C.line,
      big);
    text(s, big, { x: 8.35, y: y + 0.15, w: 4.1, h: 0.75, fontFace: NUMBER, fontSize: 34,
      bold: true, color: i === 0 ? C.teal : C.navy });
    text(s, label, { x: 8.35, y: y + 0.95, w: 4.1, h: 0.7, fontSize: 14 });
  });
  text(s, "Fragen vom Autor, Lauf 3 nach Korrekturen auf derselben Sammlung: optimistisch. "
    + "Maßgeblich ist die Handprüfung, nicht der LLM-Richter.",
  { x: 0.6, y: 5.6, w: 12.1, h: 0.75, fontSize: 15, italic: true, color: C.slate });
  s.addNotes(notes[8]);
}

// ---------- Folie 10 ----------
{
  const s = slide("DUNKEL", "Abschluss");
  text(s, "Fazit und Grenzen", { x: 0.7, y: 0.55, w: 12, h: 0.9, fontFace: HEAD, fontSize: 40,
    bold: true, color: C.white });
  const columns = [
    ["Was es zeigt", C.tealLight, ["Modell ohne Werkzeugwahl", "geprüfte Antworten mit Quellen",
      "Freigabe durch einen Menschen", "lokal und auf Deutsch"]],
    ["Grenzen", "F5C27A", ["synthetische Daten, kein Bankprodukt", "kein Identity Provider",
      "kleine Testsammlungen vom Autor"]],
    ["Nächste Schritte", "DCE8F5", ["Reranker", "unabhängig geprüfte Testsätze",
      "Single Sign-on, PII-Maskierung"]],
  ];
  columns.forEach(([head, color, bullets], i) => {
    const x = 0.7 + i * 4.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.75, w: 3.8, h: 3.4, rectRadius: 0.12,
      fill: { color: "1D3A63" }, line: { color: "2E4E7A", width: 1 } });
    text(s, head, { x: x + 0.3, y: 1.95, w: 3.2, h: 0.55, fontSize: 21, bold: true, color });
    s.addText(bullets.map((b, j) => ({ text: b, options: { bullet: true,
      breakLine: j < bullets.length - 1 } })), { x: x + 0.3, y: 2.65, w: 3.3, h: 2.85,
      fontFace: BODY, fontSize: 17, color: C.white, valign: "top", paraSpaceAfter: 8, margin: 0,
      isTextBox: true });
  });
  text(s, "Vielen Dank.", { x: 0.7, y: 5.75, w: 6, h: 0.6, fontFace: HEAD, fontSize: 26,
    bold: true, color: C.white });
  s.addNotes(notes[9]);
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
pres.writeFile({ fileName: OUT }).then((file) => console.log(`Geschrieben: ${file}`));
