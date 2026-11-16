PYTHON ?= python
PIP_AUDIT ?= pipx run pip-audit==2.10.1


.PHONY: install-lock quality typecheck test evidence-check reproduce-evidence audit deps-audit build langfuse-up langfuse-down

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
	$(PIP_AUDIT) --requirement requirements/lock-py313.txt --no-deps --disable-pip

build:
	$(PYTHON) -m build --no-isolation

LANGFUSE_COMPOSE = docker compose -p novabank-langfuse -f deploy/langfuse/docker-compose.yml --env-file deploy/langfuse/.env

langfuse-up:
	@test -f deploy/langfuse/.env || (echo "Erst: python scripts/langfuse_env.py" && exit 1)
	$(LANGFUSE_COMPOSE) up -d

langfuse-down:
	$(LANGFUSE_COMPOSE) down
