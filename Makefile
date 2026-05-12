.PHONY: all install test lint format typecheck check clean

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
