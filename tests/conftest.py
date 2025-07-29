from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

# Ensure that some suites run last and in order, any unspecified suites will before
SUITE_ORDER = [
    "TestCodebase",
]


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
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


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "use_db: mark tests that use the database")


pytest_plugins = [
    "tests.fixtures",
]
