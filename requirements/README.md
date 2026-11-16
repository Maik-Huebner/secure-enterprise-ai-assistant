# Strategie für die Lock-Datei

`lock-py313.txt` ist die exakte transitive Umgebung, die CI und Container für Python 3.13
verwenden. Zusätzlich begrenzen die Projekt-Metadaten jede direkte Laufzeit- und
Entwicklungsabhängigkeit. Erst die Lock-Datei installieren, danach das Projekt nicht editierbar
mit `--no-deps --no-build-isolation`.

PyTorch wird unter Linux (CI und Container) vor der Lock-Datei aus dem offiziellen CPU-Index
installiert. Das CPU-Wheel mit lokaler Versionskennung erfüllt die festgelegte öffentliche
Version, ohne ungenutzte CUDA-Pakete mitzubringen.

Unterstützt wird Python `>=3.13,<3.14`. Python 3.13.9 mit dieser Lock-Datei ist die
reproduzierbar geprüfte Laufzeit für Release-Prüfung, CI, Prüfung auf frischem Klon und Docker.
Ältere Python-Versionen gelten erst als unterstützt, wenn sie eine gleichwertige Prüfung auf
Lock-Ebene bestehen.

## Lock-Datei erneuern

Mit `uv` aus `pyproject.toml` auflösen, Ziel macOS 14 auf arm64. Dieses Ziel hält CUDA-Pakete aus
der Lock-Datei heraus; Linux nutzt das vorher installierte CPU-Wheel von PyTorch. `uv` behält jede
Version aus der vorhandenen Ausgabedatei, solange ein Paket nicht mit `--upgrade-package` genannt
wird; so bleibt der Diff auf die gewollten Änderungen begrenzt:

```bash
MACOSX_DEPLOYMENT_TARGET=14.0 uv pip compile pyproject.toml --extra dev \
  --python-version 3.13 --python-platform aarch64-apple-darwin \
  --no-annotate --no-header \
  --upgrade-package <name> \
  -o requirements/lock-py313.txt
```

Danach die beiden Kommentarzeilen am Anfang wiederherstellen, den Diff prüfen, die Lock-Datei in
einer frischen virtuellen Umgebung installieren und jedes Make-Ziel ausführen (auch
`make deps-audit`), dazu den Rauchtest mit dem Wheel. Einzelne transitive Versionen nicht von Hand
ändern, ohne diese Prüfung zu wiederholen.

## Bekannte Ausnahmen

Keine. `make deps-audit` läuft ohne Ausnahmeregeln, seit CrewAI und chromadb entfernt wurden (v1.4).
