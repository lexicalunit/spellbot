from unittest.mock import MagicMock

import pytest
from helpers.constants import CLIENT_AUTH, CLIENT_TOKEN, S_SPY  # type:ignore
from mocks.discord import AsyncMock, MockDM, MockTextChannel  # type: ignore
from mocks.users import ADMIN, ALL_USERS, BOT, PUNK, SERVER_MEMBERS  # type: ignore

import spellbot


class MockDiscordClient:
    def __init__(self, **kwargs):
        self.user = ADMIN
        self.channels = []

    def get_user(self, user_id):
        for user in ALL_USERS:
            if user.id == user_id:
                return user

    async def fetch_user(self, user_id):
        return self.get_user(user_id)

    def get_channel(self, channel_id):
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        return None

    async def fetch_channel(self, channel_id):
        return self.get_channel(channel_id)


@pytest.fixture
def patch_discord():
    orig = spellbot.SpellBot.__bases__
    spellbot.SpellBot.__bases__ = (MockDiscordClient,)
    yield
    spellbot.SpellBot.__bases__ = orig


def simulate_user_leaving_server(user_to_leave):
    global ALL_USERS
    ALL_USERS = [user for user in ALL_USERS if user != user_to_leave]


@pytest.mark.usefixtures("patch_discord")
@pytest.fixture
def client(monkeypatch, mocker, patch_discord, tmp_path):
    # Define which users are on this Discord server.
    global ALL_USERS
    ALL_USERS = SERVER_MEMBERS + [PUNK, BOT]

    # Keep track of strings used in the test suite.
    monkeypatch.setattr(spellbot, "s", S_SPY)

    # Don't actually begin background tasks during tests.
    monkeypatch.setattr(spellbot.SpellBot, "_begin_background_tasks", MagicMock())

    # Fallback to using sqlite for tests, but use the environment variable if it's set.
    (tmp_path / "spellbot.db").touch()
    connection_string = f"sqlite:///{tmp_path}/spellbot.db"
    db_url = spellbot.get_db_url("TEST_SPELLBOT_DB_URL", connection_string)
    bot = spellbot.SpellBot(
        token=CLIENT_TOKEN, auth=CLIENT_AUTH, db_url=db_url, mock_games=True
    )

    # Each test should have a clean slate. If we're using sqlite this is ensured
    # automatically as each test will create its own new spellbot.db file. With other
    # databases we'll have to manually clean out any existing data before each
    # test as the previous tests could have left data behind.
    for table in bot.data.metadata.tables.keys():
        bot.data.conn.execute(f"DELETE FROM {table};")

    # Make sure that all users have their send calls reset between client tests.
    for user in ALL_USERS:
        user.sent = AsyncMock()

    yield bot

    # For sqlite closing the connection when we're done isn't necessary, but for other
    # databases our test suite can quickly exhaust their connection pools.
    bot.data.conn.close()


@pytest.mark.usefixtures("client")
@pytest.fixture
def session(client):
    """
    The client creates a session when processing a command,
    we have to create one ourselves when not in a command context.
    """
    return client.data.Session()


@pytest.mark.usefixtures("client")
@pytest.fixture
def channel_maker(client):
    """Use this fixture to create channels so that we can hook them up to the client."""

    class MockChannelFactory:
        def __init__(self, next_channel_id):
            self.next_channel_id = next_channel_id

        def text(self, name="a-text-channel", members=SERVER_MEMBERS):
            channel = MockTextChannel(self.next_channel_id, name, members)
            client.channels.append(channel)  # not something you can do with a real client
            self.next_channel_id += 1
            return channel

        def dm(self):
            channel = MockDM(self.next_channel_id)
            self.next_channel_id += 1
            return channel

        def make(self, channel_type):
            if channel_type == "dm":
                return self.dm()
            return self.text()

    return MockChannelFactory(6500)
