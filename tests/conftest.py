# Make all fixtures available to all tests
from .fixtures import *  # noqa

# Ensure that some suites run last and in order, any unspecified suites will before
SUITE_ORDER = [
    "TestCodebase",
]


def pytest_collection_modifyitems(session, config, items):
    def order(f):
        suite = f.cls.__name__
        return SUITE_ORDER.index(suite) + 1 if suite in SUITE_ORDER else 0

    items.sort(key=order)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "nosession: mark test to run without a database session",
    )
