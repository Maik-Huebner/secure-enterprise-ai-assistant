"""Test-wide configuration: fast, offline, deterministic embeddings."""

import os

# Must be set before any settings object is created. Subprocesses (MCP stdio server, UI probe)
# inherit these variables.
os.environ["EMBEDDING_BACKEND"] = "hashing"
