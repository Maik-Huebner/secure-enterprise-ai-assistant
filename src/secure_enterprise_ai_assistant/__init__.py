"""Secure Enterprise AI Assistant package defaults."""

import os

# Local-first: LangChain/LangSmith tracing stays off unless an operator explicitly enables it.
os.environ.setdefault("LANGSMITH_TRACING", "false")

__version__ = "1.6.0"
