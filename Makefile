PYTHON := .venv/bin/python
PIP := .venv/bin/pip
MANAGE := $(PYTHON) manage.py

.PHONY: help venv install setup run check migrate makemigrations superuser seed reset-demo shell django-shell test test-v clean

help:
	@echo "SwedeSweets Ops commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install project dependencies from pyproject.toml"
	@echo "  make setup         Create venv, install deps, migrate database"
	@echo ""
	@echo "Django:"
	@echo "  make run           Run development server"
	@echo "  make check         Run Django system checks"
	@echo "  make migrate       Apply migrations"
	@echo "  make makemigrations Create new migrations"
	@echo "  make superuser     Create Django superuser"
	@echo "  make seed          Seed demo data"
	@echo "  make reset-demo    Reset and seed demo data"
	@echo ""
	@echo "Tools:"
	@echo "  make shell         Run shell_plus with IPython"
	@echo "  make django-shell  Run default Django shell"
	@echo "  make test          Run tests"
	@echo "  make test-v        Run verbose tests"
	@echo "  make clean         Remove Python/tool caches"

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -e .

setup: install migrate

run:
	$(MANAGE) runserver

check:
	$(MANAGE) check

migrate:
	$(MANAGE) migrate

makemigrations:
	$(MANAGE) makemigrations

superuser:
	$(MANAGE) createsuperuser

seed:
	$(MANAGE) seed_demo_data --with-demo-user

reset-demo:
	$(MANAGE) seed_demo_data --reset --with-demo-user

shell:
	$(MANAGE) shell_plus --ipython

django-shell:
	$(MANAGE) shell

test:
	$(PYTHON) -m pytest

test-v:
	$(PYTHON) -m pytest -v

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
