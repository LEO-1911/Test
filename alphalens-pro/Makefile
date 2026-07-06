.PHONY: setup dev backend frontend test lint typecheck update demo

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup:  ## Einmalig: Python-venv + Abhängigkeiten + Frontend-Pakete installieren
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	cd frontend && npm install

dev:  ## Backend (Port 8000) + Frontend (Port 5173) zusammen starten
	@trap 'kill 0' EXIT; \
	$(PY) -m uvicorn backend.api.main:app --reload --port 8000 & \
	cd frontend && npm run dev

backend:  ## Nur Backend starten
	$(PY) -m uvicorn backend.api.main:app --reload --port 8000

frontend:  ## Nur Frontend starten
	cd frontend && npm run dev

update:  ## Tägliches Daten-Update manuell anstoßen
	$(PY) -m backend.data.pipeline

demo:  ## Demo: Daten für Referenz-Ticker holen und anzeigen
	$(PY) -m backend.data.demo AAPL SAP.DE VWCE.DE

test:  ## Tests mit Coverage
	$(PY) -m pytest --cov=backend --cov-report=term-missing

lint:  ## Ruff-Linting
	$(VENV)/bin/ruff check backend tests

typecheck:  ## mypy
	$(VENV)/bin/mypy backend
