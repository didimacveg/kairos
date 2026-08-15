SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help init up down logs models migrate user test lint fmt reset estado

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

init: ## Copia .env.example a .env y genera secretos
	@test -f .env || cp .env.example .env
	@python3 scripts/gen_secrets.py
	@echo "Listo. Revisa .env antes de continuar."

up: ## Levanta toda la pila
	$(COMPOSE) up -d --build

down: ## Para la pila (los datos persisten)
	$(COMPOSE) down

logs: ## Sigue los logs del core
	$(COMPOSE) logs -f core

models: ## Descarga los modelos locales en Ollama
	$(COMPOSE) exec ollama ollama pull llama3.1:8b
	$(COMPOSE) exec ollama ollama pull nomic-embed-text

migrate: ## Crea/actualiza el esquema de base de datos
	$(COMPOSE) exec core python -m kairos.cli migrate

user: ## Crea el usuario propietario (interactivo)
	$(COMPOSE) exec core python -m kairos.cli create-user

estado: ## Revisa que todo este en pie y dice que arreglar
	bash scripts/estado.sh

test: ## Ejecuta la suite de tests del core
	$(COMPOSE) exec core pytest -q -p no:cacheprovider

lint: ## Linter + tipos
	$(COMPOSE) exec core ruff check kairos tests
	$(COMPOSE) exec core mypy kairos

fmt: ## Formatea
	$(COMPOSE) exec core ruff format kairos tests

reset: ## DESTRUCTIVO: borra volumenes y datos
	$(COMPOSE) down -v
