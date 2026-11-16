# Werkzeuge für die Dokumente in `output/`

Die Dateien in `output/` werden aus den Markdown-Quellen in `docs/` erzeugt, nie von Hand bearbeitet:

| Ergebnis | Quelle | Werkzeug |
|---|---|---|
| `output/document/Projektdokumentation_…docx` | `docs/project-documentation.md` | pandoc mit `referenz.docx` |
| `output/pdf/Projektdokumentation_…pdf` | `docs/project-documentation.md` | pandoc → HTML mit `druck.css` → Chrome |
| `output/presentation/10_Minuten_Praesentation_…pptx` | `praesentation.cjs`, Notizen aus `docs/presentation-speaker-notes.md` | pptxgenjs 3.12.0 |
| `output/pdf/10_Minuten_Praesentation_…pdf` | die PPTX-Datei | Keynote (PDF-Export) |
| `output/pdf/Sprechertext_…pdf` | `docs/presentation-speaker-notes.md` | pandoc → HTML → Chrome |

Neu erzeugen (macOS mit pandoc, Google Chrome, Keynote und Node.js):

```bash
npm ci --prefix tools/dokumente
python scripts/build_documents.py
```

- `architektur.html` ist die Quelle von `docs/assets/architektur-v2.png` (Screenshot mit Chrome
  im Headless-Modus, 1600 × 900, Faktor 1,5).
- Die Balken auf Folie 5 sind Formen statt eines Diagramm-Objekts, weil Keynote Diagramme aus
  pptxgenjs nicht darstellt und das PDF sonst eine leere Fläche zeigen würde.
- Die Node-Abhängigkeiten gehören nur zu diesem Werkzeug, nicht zur Anwendung; `node_modules/`
  ist git-ignoriert, und der Container enthält den Ordner nicht.
