.PHONY: all clean

all: clean

clean:
	@echo "cleaning runtime artifacts..."
	@rm -rf .coverage .pytest_cache .ruff_cache dist htmlcov
	@find . -name "__pycache__" -o -name "*.pyc" | xargs rm -rf
