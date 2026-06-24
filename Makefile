.PHONY: all install test lint format format-check typecheck check dev clean session-key
.PHONY: infra-stage infra-prod infra-o11y

all: check

install:
	@uv sync --frozen

test: install
	@uv run --frozen pytest -n3
	@npx vitest run

lint: install
	@echo "linting..."
	@uv run --frozen ruff check .
	@npm run lint

format: install
	@echo "formatting..."
	@uv run --frozen ruff format .
	@npm run format

format-check: install
	@echo "checking formatting..."
	@uv run --frozen ruff format --check .
	@npm run format:check

typecheck: install
	@echo "static code analysis..."
	@uv run --frozen pyright

check: lint format-check typecheck test

dev: install
	@echo "starting bot (-dmt) and api (-da)..."
	@trap 'kill 0' EXIT INT TERM; \
		uv run --frozen spellbot -dmt < /dev/null & \
		uv run --frozen spellbot -da < /dev/null & \
		wait

session-key: install
	@uv run --frozen python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

clean:
	@echo "cleaning runtime artifacts..."
	@rm -rf .coverage .pytest_cache .ruff_cache dist htmlcov
	@find . -name "__pycache__" -o -name "*.pyc" | xargs rm -rf
	@rm -rf node_modules

infra-stage:
	@echo "Deploying app infrastructure to stage..."
	@cd infrastructure/app && terraform apply -target=module.stage

infra-prod:
	@echo "Deploying app infrastructure to prod..."
	@cd infrastructure/app && terraform apply -target=module.prod

infra-o11y:
	@echo "Deploying observability infrastructure..."
	@cd infrastructure/o11y && terraform apply
