from __future__ import annotations

from _pytest.config import Config
from pytest import Item, Session

# Make all fixtures available to all tests
from .fixtures import *  # noqa

# Ensure that some suites run last and in order, any unspecified suites will before
SUITE_ORDER = [
    "TestCodebase",
]


def pytest_collection_modifyitems(session: Session, config: Config, items: list[Item]):
    def order(item: Item):
        if not item:
            return 0
        cls = getattr(item, "cls", None)
        if not cls:
            return 0
        suite = cls.__name__
        return SUITE_ORDER.index(suite) + 1 if suite in SUITE_ORDER else 0

    items.sort(key=order)


def pytest_configure(config: Config):
    config.addinivalue_line(
        "markers",
        "nosession: mark test to run without a database session",
    )
