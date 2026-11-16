PYTHON ?= python
PIP_AUDIT ?= pipx run pip-audit==2.10.1

# Temporary, documented exceptions. chromadb arrives only through CrewAI, is not used by this
# package, and has no fixed release yet. Remove together with CrewAI (v2 work package 4).
AUDIT_IGNORES = \
	--ignore-vuln PYSEC-2026-311 \
	--ignore-vuln PYSEC-2026-3813 \
	--ignore-vuln PYSEC-2026-3814 \
	--ignore-vuln PYSEC-2026-3815

.PHONY: install-lock quality typecheck test evidence-check reproduce-evidence audit deps-audit build

install-lock:
	$(PYTHON) -m pip install --no-deps -r requirements/lock-py313.txt
	$(PYTHON) -m pip install --no-deps --no-build-isolation .

quality: typecheck
	$(PYTHON) -m ruff check src scripts tests
	$(PYTHON) -m ruff format --check src scripts tests

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest -q -W error --cov --cov-report=term

evidence-check:
	$(PYTHON) scripts/check_evidence.py

reproduce-evidence:
	$(PYTHON) scripts/reproduce_evidence.py

audit:
	$(PYTHON) scripts/audit_repository.py

deps-audit:
	$(PIP_AUDIT) --requirement requirements/lock-py313.txt --no-deps --disable-pip $(AUDIT_IGNORES)

build:
	$(PYTHON) -m build --no-isolation
