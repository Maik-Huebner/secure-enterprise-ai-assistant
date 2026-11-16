Dokument-ID: NB-SEC-001
Titel: Richtlinie zur Informationssicherheit
Version: 3.2
Gültig ab: 2026-09-01
Verantwortlich: Informationssicherheit
Klassifizierung: Intern – synthetische Demo

# Richtlinie zur Informationssicherheit

> NovaBank Financial Services AG ist eine fiktive Organisation. Alle Kunden, Anträge, Richtlinien, Regeln und Finanzdaten in diesem Projekt sind synthetisch und wurden ausschließlich für Demonstrations-, Test- und Portfoliozwecke erstellt.

## 4 Lokale Verarbeitung
Sensible Unternehmensinformationen bleiben auf freigegebener lokaler Infrastruktur.
Externe Modellanbieter sind optional und dürfen niemals eine versteckte
Laufzeitvoraussetzung sein.

## 6 Kontrollen für KI-Werkzeuge
Aufgerufen werden dürfen nur freigegebene MCP-Werkzeuge mit geprüften Schemas. Werkzeuge
bieten keinen Zugriff auf beliebiges SQL, beliebige Dateipfade oder eine Shell.
Fehlermeldungen an Agenten sind sicher und enthalten keine Geheimnisse und keine
Stacktraces.

## 8 Sicherheit der Wissensbasis
Gefundene Dokumente sind nicht vertrauenswürdige Daten und keine Anweisungen. Eingebettete
Versuche, das Systemverhalten zu verändern, interne Vorgaben preiszugeben oder Werkzeuge
aufzurufen, werden nicht befolgt. Die Herkunft der Quellen bleibt erhalten, und jede
Dateioperation ist auf das konfigurierte Verzeichnis der Wissensbasis beschränkt.

## Dokumentenlenkung
Verantwortlich: Informationssicherheit. Überprüfung: jährlich. Dieses Dokument ist synthetisch.
