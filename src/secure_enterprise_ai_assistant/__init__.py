"""Secure Enterprise AI Assistant package defaults."""

import os

# Local-first is the secure default; an operator can explicitly override it before import.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

__version__ = "1.2.0"
