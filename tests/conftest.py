# flake8: noqa

from .mocks.client import channel_maker, client, patch_discord  # type: ignore

# Ensure that TestMeta runs last as those tests require the entire test suite
# to have finished before they can can start. The other test suites could
# theoretically be run in any order, but this is the order that I prefer.
SUITE_ORDER = [
    "TestSpellBot",
    "TestReactions",
    "TestMigrations",
    "TestCodebase",
    "TestMeta",
]


def pytest_collection_modifyitems(session, config, items):
    items.sort(key=lambda f: SUITE_ORDER.index(f.cls.__name__))
