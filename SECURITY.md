# Sicherheitsrichtlinie

## Geltungsbereich

Dieses Repository ist ein Referenzsystem für ein Portfolio und arbeitet nur mit synthetischen
Daten. Es zeigt sicherheitsorientierte Entwurfsentscheidungen, ist aber weder ein zertifiziertes
Sicherheitsprodukt noch ein produktives Bankensystem.

## Schwachstellen melden

Öffne für eine vermutete Schwachstelle, die ein Geheimnis preisgeben oder Missbrauch ermöglichen
könnte, kein öffentliches Issue. Nutze die private Schwachstellenmeldung von GitHub für dieses
Repository, sofern sie verfügbar ist. Nenne die betroffene Version, die Schritte zum
Nachstellen, die Auswirkung und gern einen Vorschlag zur Behebung. Schicke in einer Meldung keine
echten Kunden-, Finanz-, Identitäts- oder Anmeldedaten mit.

## Unterstützte Versionen

Sicherheitskorrekturen gibt es nur für den aktuellen Standard-Branch. Ältere Tags bleiben
unveränderte Portfolio-Stände und können Grenzen enthalten, die zum Zeitpunkt der Veröffentlichung
dokumentiert waren.

## Sicherheitsgrenzen

Der unterstützte Weg nutzt synthetische Fälle und Richtlinien, vier freigegebene MCP-Werkzeuge
und keinen externen Anbieter. Anmeldung mit JWT, rollenbasierte Berechtigungen, Vier-Augen-Freigabe
und ein Audit-Log mit Hash-Kette sind enthalten. Verschlüsselte Speicherung, eine Sandbox für
Schadsoftware, die Weiterleitung des Audit-Logs in einen manipulationssicheren Speicher und ein
formaler Penetrationstest gehören nicht zum aktuellen Umfang. Siehe
[docs/security.md](docs/security.md) und [RESPONSIBLE_USE.md](RESPONSIBLE_USE.md).
