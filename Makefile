.PHONY: run test lint format seed clean help

PYTHON ?= python
UVICORN ?= uvicorn
PYTEST ?= pytest
RUFF ?= ruff
MYPY ?= mypy

help:
	@echo "Available commands:"
	@echo "  make run    - Run FastAPI development server"
	@echo "  make test   - Run test suite with pytest"
	@echo "  make lint   - Run ruff and mypy linters"
	@echo "  make format - Format code with ruff"
	@echo "  make seed   - Seed database with 10 sample products"
	@echo "  make clean  - Clean cache and temporary files"

run:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

test:
	$(PYTEST) -v tests

lint:
	$(RUFF) check app tests
	$(RUFF) format --check app tests
	$(MYPY) app tests

format:
	$(RUFF) format app tests
	$(RUFF) check --fix app tests

seed:
	$(PYTHON) -m app.db.seed

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('.*cache')]"
