PYTHON ?= python

.PHONY: install-lock quality test evidence-check reproduce-evidence audit build

install-lock:
	$(PYTHON) -m pip install --no-deps -r requirements/lock-py313.txt
	$(PYTHON) -m pip install --no-deps --no-build-isolation .

quality:
	$(PYTHON) -m ruff check src scripts tests
	$(PYTHON) -m ruff format --check src scripts tests

test:
	$(PYTHON) -m pytest -q -W error

evidence-check:
	$(PYTHON) scripts/check_evidence.py

reproduce-evidence:
	$(PYTHON) scripts/reproduce_evidence.py

audit:
	$(PYTHON) scripts/audit_repository.py

build:
	$(PYTHON) -m build --no-isolation
