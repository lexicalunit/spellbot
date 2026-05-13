.PHONY: all install test lint format typecheck check clean
.PHONY: infra-stage infra-prod infra-o11y

all: check

install:
	@uv sync --frozen

test: install
	@uv run --frozen pytest -n3

lint: install
	@echo "linting..."
	@uv run --frozen ruff check .

format: install
	@echo "formatting..."
	@uv run --frozen ruff format .

typecheck: install
	@echo "static code analysis..."
	@uv run --frozen pyright

check: lint typecheck test

clean:
	@echo "cleaning runtime artifacts..."
	@rm -rf .coverage .pytest_cache .ruff_cache dist htmlcov
	@find . -name "__pycache__" -o -name "*.pyc" | xargs rm -rf

infra-stage:
	@echo "Deploying app infrastructure to stage..."
	@cd infrastructure/app && terraform apply -target=module.stage

infra-prod:
	@echo "Deploying app infrastructure to prod..."
	@cd infrastructure/app && terraform apply -target=module.prod

infra-o11y:
	@echo "Deploying observability infrastructure..."
	@cd infrastructure/o11y && terraform apply
