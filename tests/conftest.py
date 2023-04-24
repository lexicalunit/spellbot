from __future__ import annotations

import pytest
from _pytest.config import Config

# Ensure that some suites run last and in order, any unspecified suites will before
SUITE_ORDER = [
    "TestCodebase",
]


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: Config,
    items: list[pytest.Item],
) -> None:
    def order(item: pytest.Item) -> int:
        if not item:  # pragma: no cover
            return 0
        cls = getattr(item, "cls", None)
        if not cls:  # pragma: no cover
            return 0
        suite = cls.__name__
        return SUITE_ORDER.index(suite) + 1 if suite in SUITE_ORDER else 0

    items.sort(key=order)


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers",
        "nosession: mark test to run without a database session",
    )


pytest_plugins = [
    "tests.fixtures",
]
