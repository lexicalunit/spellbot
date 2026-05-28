# Python Development Guidelines

- Do not put import statements inside functions or classes, unless it is necessary to avoid circular imports or to improve performance.
- Do not name symbols starting with an underscore, unless it is to indicate that they are unused. Do not name files starting with an underscore either. Generally speaking, do not use an underscore at the beginning of a name to indicate that it is private.
- When running unit tests use `-n3` to run them in parallel.
- Upon file save unused imports will be automatically removed, so do not add an import to a file if it is unused. You must write code that uses the import before you add the import to the file.
- Do not run `ruff` or `pyright` manually, they will run as part of the full test suite.
- Do not add docstrings to modules.
- Do not add docstrings to test functions.
