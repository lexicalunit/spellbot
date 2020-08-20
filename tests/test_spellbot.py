import inspect
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytz

import spellbot
from spellbot.constants import THUMB_URL
from spellbot.data import Event, Game, User

from .constants import CLIENT_TOKEN, TEST_DATA_ROOT
from .mocks.discord import MockAttachment, MockChannel, MockMessage, MockPayload
from .mocks.users import (
    ADAM,
    ADMIN,
    ADMIN_ROLE,
    AMY,
    BOT,
    BUDDY,
    DUDE,
    FRIEND,
    GUY,
    JACOB,
    JR,
    PUNK,
    SERVER_MEMBERS,
    TOM,
)
from .test_meta import SNAPSHOTS_USED

##############################
# Test Suite Utilities
##############################


def someone():
    """Returns some non-admin user"""
    return random.choice(list(filter(lambda member: member != ADMIN, SERVER_MEMBERS)))


def an_admin():
    """Returns a random non-admin user with the SpellBot Admin role"""
    cond = lambda member: member != ADMIN and ADMIN_ROLE in member.roles
    return random.choice(list(filter(cond, SERVER_MEMBERS)))


def not_an_admin():
    """Returns a random non-admin user without the SpellBot Admin role"""
    cond = lambda member: member != ADMIN and ADMIN_ROLE not in member.roles
    return random.choice(list(filter(cond, SERVER_MEMBERS)))


def is_discord_file(obj):
    """Returns true if the given object is a discord File object."""
    return (obj.__class__.__name__) == "File"


def user_has_game(client, user):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user and db_user.game is not None
    session.close()
    return rvalue


def game_json_for(client, user):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user.game.to_json() if db_user and db_user.game else None
    session.close()
    return rvalue


def user_json_for(client, user):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user.to_json() if db_user else None
    session.close()
    return rvalue


def game_embed_for(client, user, ready, message=None, dm=False):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user.game.to_embed(dm) if db_user and db_user.game else None
    session.close()
    if ready:
        assert db_user.game.status != "pending"
    if message:
        assert db_user.game.message == message
    return rvalue.to_dict() if rvalue else None


def all_games(client):
    session = client.data.Session()
    games = session.query(Game).all()
    rvalue = [json.loads(str(game)) for game in games]
    session.close()
    return rvalue


def all_events(client):
    session = client.data.Session()
    events = session.query(Event).all()
    rvalue = [json.loads(str(event)) for event in events]
    session.close()
    return rvalue


##############################
# Test Fixtures
##############################


@pytest.fixture(autouse=True, scope="session")
def set_random_seed():
    random.seed(0)


@pytest.fixture
def snap(snapshot):
    snapshot.snapshot_dir = Path("tests") / "snapshots"
    snap.counter = 0

    def match(obj):
        test = inspect.stack()[1].function
        snapshot_file = f"{test}_{snap.counter}.txt"
        snapshot.assert_match(str(obj), snapshot_file)
        snap.counter += 1
        SNAPSHOTS_USED.add(snapshot_file)

    return match


##############################
# Test Suite
##############################


@pytest.mark.asyncio
class TestSpellBot:
    async def test_init(self, client, channel_maker):
        assert client.token == CLIENT_TOKEN

    async def test_on_ready(self, client, channel_maker):
        await client.on_ready()

    async def test_on_message_non_text(self, client, channel_maker):
        channel = MockChannel(6, "voice")
        await client.on_message(MockMessage(someone(), channel, "!help"))
        channel.sent.assert_not_called()

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_is_admin(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        assert spellbot.is_admin(channel, not_an_admin()) == False
        assert spellbot.is_admin(channel, an_admin()) == True

    async def test_parse_opts(self):
        assert spellbot.parse_opts(["a", "B", "c"]) == {
            "message": None,
            "params": ["a", "B", "c"],
            "size": 4,
            "tags": [],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "~B", "c"]) == {
            "message": None,
            "params": ["a", "c"],
            "size": 4,
            "tags": ["b"],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "size:5", "c"]) == {
            "message": None,
            "params": ["a", "c"],
            "size": 5,
            "tags": [],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "size:fancy", "c"]) == {
            "message": None,
            "params": ["a", "c"],
            "size": None,
            "tags": [],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "size:", "5", "c"]) == {
            "message": None,
            "params": ["a", "c"],
            "size": 5,
            "tags": [],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "size:", "fancy", "c"]) == {
            "message": None,
            "params": ["a", "fancy", "c"],
            "size": None,
            "tags": [],
            "system": "spelltable",
        }

        # TODO: Coverage for all functionality of parse_opts could be here, but it is
        #       actually covered in other places in these tests so, shrug...

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_no_request(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(someone(), channel, "!"))
        await client.on_message(MockMessage(someone(), channel, "!!"))
        await client.on_message(MockMessage(someone(), channel, "!!!"))
        await client.on_message(MockMessage(someone(), channel, "!   "))
        await client.on_message(MockMessage(someone(), channel, "!   !"))
        await client.on_message(MockMessage(someone(), channel, " !   !"))
        channel.sent.assert_not_called()

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_ambiguous_request(
        self, client, channel_maker, channel_type
    ):
        author = someone()
        channel = channel_maker.make(channel_type)
        msg = MockMessage(author, channel, "!l")
        if hasattr(channel, "recipient"):
            assert channel.recipient == author
        await client.on_message(msg)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, that's not a command."
            " Did you mean to use one of these commands: !leave, !lfg?"
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_invalid_request(self, client, channel_maker, channel_type):
        dm = channel_maker.make(channel_type)
        author = someone()
        await client.on_message(MockMessage(author, dm, "!xeno"))
        assert dm.last_sent_response == (
            f'Sorry <@{author.id}>, there is no "xeno" command.'
            ' Try "!spellbot help" for usage help.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_from_a_bot(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(BOT, channel, "!help"))
        assert len(channel.all_sent_calls) == 0

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_help(self, client, channel_maker, channel_type, snap):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!help"))
        for response in author.all_sent_responses:
            snap(response)
        assert len(author.all_sent_calls) == 3

    async def test_on_message_help_includes_confirmation_message_in_text_channel(
        self, client, channel_maker
    ):
        author = someone()
        channel = channel_maker.make("text")
        await client.on_message(MockMessage(author, channel, "!help"))
        assert len(channel.all_sent_calls) == 1
        assert channel.last_sent_response == (
            f"Right on <@{author.id}>, I'll send you a Direct Message with details."
        )

    async def test_on_message_help_does_not_include_confirmation_message_in_dm(
        self, client, channel_maker
    ):
        author = someone()
        channel = channel_maker.make("dm")
        await client.on_message(MockMessage(author, channel, "!help"))
        assert len(channel.all_sent_calls) == 0

    async def test_on_message_spellbot_dm(self, client, channel_maker):
        author = an_admin()
        dm = channel_maker.dm()
        await client.on_message(MockMessage(author, dm, "!spellbot channels foo"))
        assert author.last_sent_response == (
            f"Hello <@{author.id}>! That command only works in text channels."
        )

    async def test_on_message_spellbot_non_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot channels foo"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_spellbot_no_subcommand(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, please provide a subcommand when using this command."
        )

    async def test_on_message_spellbot_bad_subcommand(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot foo"))
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but the subcommand "foo" is not recognized.'
        )

    async def test_on_message_spellbot_channels_none(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot channels"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but please provide a list of channels."
            " Like #bot-commands, for example."
        )

    async def test_on_message_spellbot_channels_all_bad(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot channels foo"))
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but "foo" is not a valid channel. Try using # to'
            ' mention the channels you want or using "all" if you want me to operate'
            " in all channels."
        )

    async def test_on_message_spellbot_channels_one_bad_one_good(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        author = an_admin()
        cmd = f"!spellbot channels foo <#{channel.id}>"
        await client.on_message(MockMessage(author, channel, cmd))
        assert len(channel.all_sent_responses) == 2
        assert channel.all_sent_responses[0] == (
            f'Sorry <@{author.id}>, but "foo" is not a valid channel. Try using # to'
            ' mention the channels you want or using "all" if you want me to operate'
            " in all channels."
        )
        assert channel.all_sent_responses[1] == (
            f"Ok <@{author.id}>, I will now operate within: <#{channel.id}>"
        )

    async def test_on_message_spellbot_channels_with_bad_ref(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels <#{channel.id + 1}>")
        )
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but "<#{channel.id + 1}>" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )
        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you we're not in any pending games."
        )

    async def test_on_message_spellbot_channels_with_invalid(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels #{channel.id}")
        )
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but "#{channel.id}" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )

        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you we're not in any pending games."
        )

    async def test_on_message_spellbot_channels_no_mention(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels #{channel.name}")
        )
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but "#{channel.name}" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )

        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you we're not in any pending games."
        )

    async def test_on_message_spellbot_channels(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        foo = channel_maker.text("foo")
        bar = channel_maker.text("bar")
        baz = channel_maker.text("baz")
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels <#{channel.id}>")
        )
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I will now operate within: <#{channel.id}>"
        )
        cmd = f"!spellbot channels <#{foo.id}> <#{bar.id}> <#{baz.id}>"
        await client.on_message(MockMessage(author, channel, cmd))
        resp = (
            f"Ok <@{author.id}>, I will now operate within:"
            f" <#{foo.id}>, <#{bar.id}>, <#{baz.id}>"
        )
        assert channel.last_sent_response == resp
        await client.on_message(MockMessage(author, channel, "!help"))  # bad channel now
        assert channel.last_sent_response == resp

        await client.on_message(MockMessage(author, foo, "!spellbot channels all"))
        assert foo.last_sent_response == (
            f"Ok <@{author.id}>, I will now operate within: all channels"
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_about(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(someone(), channel, "!about"))
        assert len(channel.all_sent_calls) == 1

        about = channel.last_sent_embed
        assert about["title"] == "SpellBot"
        assert about["url"] == "http://spellbot.io/"
        assert about["description"] == (
            "_The Discord bot for [SpellTable](https://www.spelltable.com/)._\n"
            "\n"
            "Use the command `!help` for usage details. Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
            "\n"
            "[🔗 Add SpellBot to your Discord!](https://discordapp.com/api/oauth2"
            "/authorize?client_id=725510263251402832&permissions=92224&scope=bot)\n"
            "\n"
            "[👍 Give SpellBot a vote on top.gg!]"
            "(https://top.gg/bot/725510263251402832/vote)\n"
            "\n"
            "💜 Help keep SpellBot running by "
            "[supporting me on Ko-fi!](https://ko-fi.com/Y8Y51VTHZ)"
        )
        assert about["thumbnail"]["url"] == THUMB_URL

        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Author"] == "[@lexicalunit](https://github.com/lexicalunit)"

        version = spellbot.__version__
        assert fields["Version"] == (
            f"[{version}](https://pypi.org/project/spellbot/{version}/)"
        )

    async def test_on_message_spellbot_prefix_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but please provide a prefix string."
        )

    async def test_on_message_spellbot_prefix(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix $"))
        assert channel.last_sent_response == (
            f'Ok <@{author.id}>, I will now use "$" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "$about"))
        assert channel.last_sent_embed["url"] == "http://spellbot.io/"
        await client.on_message(MockMessage(author, channel, "$spellbot prefix $"))
        assert channel.last_sent_response == (
            f'Ok <@{author.id}>, I will now use "$" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "$spellbot prefix !"))
        assert channel.last_sent_response == (
            f'Ok <@{author.id}>, I will now use "!" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "!spellbot prefix )"))
        assert channel.last_sent_response == (
            f'Ok <@{author.id}>, I will now use ")" as my command prefix on this server.'
        )

    async def test_on_message_spellbot_expire_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but please provide a number of minutes."
        )

    async def test_on_message_spellbot_expire_bad(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire world"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but game expiration time"
            " should be between 10 and 60 minutes."
        )

    async def test_on_message_spellbot_expire(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire 45"))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, game expiration time on this"
            " server has been set to 45 minutes."
        )

    async def test_on_message_spellbot_config(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix $"))
        await client.on_message(MockMessage(author, channel, "$spellbot expire 45"))
        await client.on_message(MockMessage(author, channel, "$spellbot config"))

        about = channel.last_sent_embed
        assert about["title"] == "SpellBot Server Config"
        assert about["footer"]["text"] == f"Config for Guild ID: {channel.guild.id}"
        assert about["thumbnail"]["url"] == THUMB_URL
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Inactivity expiration time"] == "45 minutes"
        assert fields["Active channels"] == "all"

        foo = channel_maker.text("foo")
        bar = channel_maker.text("bar")
        channels_cmd = f"$spellbot channels <#{channel.id}> <#{foo.id}> <#{bar.id}>"
        await client.on_message(MockMessage(author, channel, channels_cmd))
        await client.on_message(MockMessage(author, channel, "$spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Active channels"] == f"<#{channel.id}>, <#{foo.id}>, <#{bar.id}>"

    async def test_on_message_game_with_too_many_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE, AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, you mentioned too many people."
            " I expected 4 players to be mentioned."
        )

    async def test_on_message_game_with_too_few_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, you mentioned too few people."
            " I expected 4 players to be mentioned."
        )

    async def test_on_message_game_with_too_many_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        tags = ["one", "two", "three", "four", "five", "six"]
        tags_str = " ".join([f"~{tag}" for tag in tags])
        cmd = f"!game {mentions_str} {tags_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you can not use more than 5 tags."
        )

    async def test_on_message_game_with_size_bad(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str} size:100"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_game_non_admin(self, client, channel_maker):
        channel = channel_maker.text()
        author = not_an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_game_message_too_long(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "foo bar baz" * 100
        cmd = f"!game {mentions_str} msg: {message}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the optional game message"
            " must be shorter than 255 characters."
        )

    async def test_on_message_game(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == []
        assert game_json_for(client, GUY)["message"] == None

    async def test_on_message_game_with_message(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} msg: {message}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True, message=message)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == []
        assert game_json_for(client, GUY)["message"] == message

    async def test_on_message_game_with_message_and_tags(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} msg: {message} ~a ~b ~c"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True, message=message)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, GUY)["message"] == message

        mentions = [ADAM, AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} size: 2 msg: {message} ~a ~b ~c"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[1]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{AMY.id}>, <@{ADAM.id}>"
        )
        player_response = game_embed_for(client, ADAM, True, message=message)
        assert ADAM.last_sent_embed == player_response
        assert AMY.last_sent_embed == player_response

        assert game_json_for(client, ADAM)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, ADAM)["message"] == message

    async def test_on_message_game_with_tags_and_message(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} ~a ~b ~c msg:{message}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True, message=message)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, GUY)["message"] == message

    async def test_on_message_game_multiple_times(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        mentions = [AMY, JR, ADAM, FRIEND]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[1]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{AMY.id}>, <@{ADAM.id}>,"
            f" <@{JR.id}>, <@{FRIEND.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert AMY.last_sent_embed == player_response
        assert JR.last_sent_embed == player_response
        assert ADAM.last_sent_embed == player_response

    async def test_ensure_server_exists(self, client):
        session = client.data.Session()
        server = client.ensure_server_exists(session, 5)
        session.commit()
        assert json.loads(str(server)) == {
            "channels": [],
            "guild_xid": 5,
            "prefix": "!",
            "expire": 30,
            "teams": [],
        }

    async def test_on_message_event_no_data(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!event"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you must include an attachment containing"
            " event data with this command."
        )

    async def test_on_message_event_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        message = MockMessage(author, channel, "!event", attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, please include the column names from the CSV file"
            " too identify the players' discord names."
        )

    async def test_on_message_event_invalid_player_count(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        message = MockMessage(author, channel, "!event a", attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the player count must be between 2 and 4."
        )

    async def test_on_message_event_missing_player(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        warning = (
            "**Warning:** Event file is missing a player name on row 1."
            f' SpellBot will **NOT** create a game for the players: "{AMY.name}", "".'
        )
        assert warning in channel.all_sent_responses
        assert channel.last_sent_response == (
            f"Hey <@{author.id}>, no games were created for this event."
            " Please address any warnings and try again."
        )

    async def test_on_message_event_no_header(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the attached CSV file is missing a header."
        )

    async def test_on_message_event_no_header_v2(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes("1,2,3\n4,5,6\n7,8,9", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the attached CSV file is missing a header."
        )

    async def test_on_message_event_not_csv(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        txt_file = MockAttachment("event.txt", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[txt_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the file is not a CSV file."
            ' Make sure the filename ends with ".csv" please.'
        )

    async def test_on_message_event_missing_discord_user(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{PUNK.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)

        warning = (
            '**Warning:** On row 1 the username "punk" is not on this server. '
            "SpellBot will **NOT** create a game for the players:"
            f' "{AMY.name}", "{PUNK.name}".'
        )
        assert warning in channel.all_sent_responses

    async def test_on_message_event_not_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_event_message_too_long(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "foo bar baz" * 100
        comment = f"!event player1 player2 msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the optional game message"
            " must be shorter than 255 characters."
        )

    async def test_on_message_event_with_too_many_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name}#1234,@{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        tags = ["one", "two", "three", "four", "five", "six"]
        tags_str = " ".join([f"~{tag}" for tag in tags])
        comment = f"!event player1 player2 {tags_str}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you can not use more than 5 tags."
        )

    async def test_on_message_event_duplicate_user(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(
            "player1,player2\n"
            f"{AMY.name}#1234,@{JR.name}\n"
            f"{ADAM.name},{AMY.name}\n",
            "utf-8",
        )
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"**Error:** The user {AMY.name} appears in more than one pairing in this"
            " event file! I first noticed this duplicate on row 2 which contains the"
            f' players: "{ADAM.name}", "{AMY.name}". Please resolve this issue and try'
            " again."
        )

    async def test_on_message_event(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(
            "player1,player2\n"
            f"{AMY.name}#1234,@{JR.name}\n"
            f"{ADAM.name},{GUY.name}\n",
            "utf-8",
        )
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 2 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

    async def test_on_message_event_with_message(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

    async def test_on_message_event_with_message_and_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 msg: {opt} ~a ~b ~c"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )
        assert game_json_for(client, AMY)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, AMY)["message"] == "an message override"
        assert game_json_for(client, AMY) == game_json_for(client, JR)

    async def test_on_message_event_with_tags_and_message(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 ~a ~b ~c msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )
        assert game_json_for(client, AMY)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, AMY)["message"] == "an message override"
        assert game_json_for(client, AMY) == game_json_for(client, JR)

        data = bytes(f"player1,player2\n{ADAM.name},{GUY.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 ~a ~b ~c msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[1]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )
        assert game_json_for(client, ADAM)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, ADAM)["message"] == "an message override"
        assert game_json_for(client, ADAM) == game_json_for(client, GUY)

    async def test_on_message_begin_not_admin(self, client, channel_maker):
        channel = channel_maker.text()
        admin = an_admin()
        not_admin = not_an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(admin, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{admin.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(not_admin, channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            f"<@{not_admin.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_begin_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!begin"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, please provide the event ID with that command."
        )

    async def test_on_message_begin_bad_param(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!begin sock"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but I can't find an event with that ID."
        )

    async def test_on_message_begin_event_not_found(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id + 1}"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but I can't find an event with that ID."
        )

    async def test_on_message_begin_event(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: {AMY.name}, {JR.name}"
        )
        player_response = game_embed_for(client, AMY, True)
        assert AMY.last_sent_embed == player_response
        assert JR.last_sent_embed == player_response

    async def test_on_message_begin_event_with_message(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "this is an optional message"
        comment = f"!event player1 player2 msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: {AMY.name}, {JR.name}"
        )
        player_response = game_embed_for(client, AMY, True, message=opt)
        assert AMY.last_sent_embed == player_response
        assert JR.last_sent_embed == player_response

    async def test_on_message_begin_event_when_user_left(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        client.mock_disconnect_user(AMY)

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            "**Warning:** A user left the server since this event was created."
            " SpellBot did **NOT** start the game for the players:"
            f" {AMY.name}, {JR.name}."
        )

    async def test_on_message_begin_event_already(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but that event has already started"
            " and can not be started again."
        )

    async def test_on_message_lfg_dm(self, client, channel_maker):
        channel = channel_maker.dm()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert author.last_sent_response == (
            f"Hello <@{author.id}>! That command only works in text channels."
        )

    async def test_on_message_lfg_size_too_much(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:10"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_too_many_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        author = DUDE
        mentions = [FRIEND, GUY, BUDDY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you've mentioned too many players"
            " for that size game."
        )

    async def test_on_message_lfg_mention_already(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg"))

        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{JR.id}>, but <@{AMY.id}> is already in another"
            " pending game and can't be invited."
        )

    async def test_on_message_lfg_size_too_little(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:1"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_size_not_number(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:x"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_too_many_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg ~a ~b ~c ~d ~e ~f"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you can not use more than 5 tags."
        )

    async def test_on_message_lfg_already(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        post = channel.last_sent_message
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert channel.last_sent_response == (
            f"I found a game for you, <@{author.id}>. You have been signed up for it!"
            " Go to game post: https://discordapp.com/channels/"
            f"{channel.guild.id}/{channel.id}/{post.id}"
        )

    async def test_on_message_lfg(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert channel.last_sent_embed == game_embed_for(client, author, False)

    async def test_on_message_lfg_mtgo(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(JR, channel, "!lfg size:2 ~mtgo"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        game = game_json_for(client, ADAM)
        assert game["system"] == "mtgo"
        assert game["tags"] == []
        assert game_embed_for(client, ADAM, True) == {
            "color": 5914365,
            "description": "Please exchange MTGO contact information and head over there"
            " to play!",
            "fields": [
                {"inline": False, "name": "Players", "value": f"<@{ADAM.id}>, <@{JR.id}>"}
            ],
            "footer": {"text": f"SpellBot Reference #SB{game['id']}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    async def test_on_message_lfg_arena(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(JR, channel, "!lfg size:2 ~arena"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        game = game_json_for(client, ADAM)
        assert game["system"] == "arena"
        assert game["tags"] == []
        assert game_embed_for(client, ADAM, True) == {
            "color": 5914365,
            "description": "Please exchange Arena contact information and head over there"
            " to play!",
            "fields": [
                {"inline": False, "name": "Players", "value": f"<@{ADAM.id}>, <@{JR.id}>"}
            ],
            "footer": {"text": f"SpellBot Reference #SB{game['id']}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    async def test_on_message_lfg_with_size(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:2"))
        assert "1 more player" in channel.last_sent_embed["title"]

    async def test_on_message_lfg_with_size_with_space(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size: 2"))
        assert "1 more player" in channel.last_sent_embed["title"]

    async def test_on_message_lfg_with_tags(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(ADAM, channel, "!lfg ~modern ~no-ban-list"))
        assert {
            "inline": True,
            "name": "Tags",
            "value": "modern, no-ban-list",
        } in channel.last_sent_embed["fields"]

        await client.on_message(MockMessage(JR, channel, "!lfg ~modern"))
        assert {
            "inline": True,
            "name": "Tags",
            "value": "modern",
        } in channel.last_sent_embed["fields"]

    async def test_on_message_lfg_with_invite(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert len(channel.all_sent_calls) == 0
        assert AMY.last_sent_response == (
            f"Hello <@{AMY.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )
        assert ADAM.last_sent_response == (
            f"Hello <@{ADAM.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )

    async def test_on_message_lfg_with_invite_all_confirmed(self, client, channel_maker):
        channel = channel_maker.text()
        dm = channel_maker.dm()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert len(channel.all_sent_calls) == 0
        assert AMY.last_sent_response == (
            f"Hello <@{AMY.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )
        assert ADAM.last_sent_response == (
            f"Hello <@{ADAM.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )

        await client.on_message(MockMessage(AMY, dm, "yes"))
        assert AMY.last_sent_response == (
            f"Thanks <@{AMY.id}>, your invitation has been confirmed!"
        )
        assert len(channel.all_sent_calls) == 0

        await client.on_message(MockMessage(AMY, dm, "yes"))
        assert AMY.last_sent_response == (
            f"Hi <@{AMY.id}>, just letting you know that your invitation"
            " was already confirmed."
        )
        assert len(channel.all_sent_calls) == 0

        await client.on_message(MockMessage(ADAM, dm, "yes"))
        assert ADAM.last_sent_response == (
            f"Thanks <@{ADAM.id}>, your invitation has been confirmed!"
        )

        assert channel.last_sent_embed == game_embed_for(client, JR, False)
        assert channel.last_sent_embed == game_embed_for(client, AMY, False)
        assert channel.last_sent_embed == game_embed_for(client, ADAM, False)

    async def test_on_message_lfg_with_invite_some_confirmed(self, client, channel_maker):
        channel = channel_maker.text()
        dm = channel_maker.dm()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert len(channel.all_sent_calls) == 0
        assert AMY.last_sent_response == (
            f"Hello <@{AMY.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )
        assert ADAM.last_sent_response == (
            f"Hello <@{ADAM.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )

        await client.on_message(MockMessage(AMY, dm, "yes"))
        assert AMY.last_sent_response == (
            f"Thanks <@{AMY.id}>, your invitation has been confirmed!"
        )
        assert len(channel.all_sent_calls) == 0

        await client.on_message(MockMessage(DUDE, dm, "yes"))
        assert DUDE.last_sent_response == (
            f"Sorry <@{DUDE.id}>, but you do not currently have any pending invitations."
        )
        assert len(channel.all_sent_calls) == 0

        await client.on_message(MockMessage(ADAM, dm, "no"))
        assert ADAM.last_sent_response == f"Thank you for your response, <@{ADAM.id}>."

        assert channel.last_sent_embed == game_embed_for(client, JR, False)
        assert channel.last_sent_embed == game_embed_for(client, AMY, False)
        assert not user_has_game(client, ADAM)

    async def test_on_message_leave(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert channel.last_sent_embed == game_embed_for(client, author, False)
        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, you've been removed from the pending game"
            " that you were signed up for."
        )

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_message_leave_already(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you we're not in any pending games."
        )

    async def test_on_raw_reaction_add_irrelevant(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="👍",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) == None

    async def test_on_raw_reaction_add_bad_channel(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id + 1,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) == None

    async def test_on_raw_reaction_add_self(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADMIN.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADMIN,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADMIN, False) == None

    async def test_on_raw_reaction_add_bad_message(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id + 1,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) == None

    async def test_on_raw_reaction_add_plus_unauth_channel(self, client, channel_maker):
        channel_a = channel_maker.text("a")
        channel_b = channel_maker.text("b")

        await client.on_message(MockMessage(GUY, channel_a, "!lfg"))
        message = channel_a.last_sent_message

        lock_up = MockMessage(
            an_admin(), channel_a, f"!spellbot channels <#{channel_b.id}>"
        )
        await client.on_message(lock_up)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel_a.id,
            guild_id=channel_a.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) == None

    async def test_on_raw_reaction_add_plus_not_a_game(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!leave"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert message.reactions == []

    async def test_on_raw_reaction_add_plus_twice(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        await client.on_raw_reaction_add(payload)
        assert len(ADAM.all_sent_calls) == 0

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus_already(self, client, channel_maker):
        channel = channel_maker.text()

        # first game
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)

        # second game
        await client.on_message(MockMessage(JR, channel, "!lfg ~modern"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert len(all_games(client)) == 2
        assert game_embed_for(client, ADAM, False) != game_embed_for(client, GUY, False)

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert "2 more players" in game_embed_for(client, ADAM, False)["title"]

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus_complete(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        ready = game_embed_for(client, ADAM, True)
        assert GUY.last_sent_embed == ready
        assert ADAM.last_sent_embed == ready

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus_after_disconnect(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        message = channel.last_sent_message

        client.mock_disconnect_user(GUY)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert "1 more player" in game_embed_for(client, ADAM, False)["title"]

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus_then_minus(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message

        assert not user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➖",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert not user_has_game(client, ADAM)

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_minus_to_empty_game(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message

        payload = MockPayload(
            user_id=GUY.id,
            message_id=message.id,
            emoji="➖",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=GUY,
        )
        await client.on_raw_reaction_add(payload)
        assert not user_has_game(client, GUY)

        session = client.data.Session()
        games = session.query(Game).all()
        rvalue = [game.to_embed().to_dict() for game in games]
        session.close()
        assert rvalue == [
            {
                "color": 5914365,
                "description": "To join/leave this game, react with ➕/➖.",
                "footer": {"text": f"SpellBot Reference #SB{games[0].id}"},
                "thumbnail": {"url": THUMB_URL},
                "title": "**Waiting for 4 more players to join...**",
                "type": "rich",
            },
        ]

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_minus_when_not_in_game(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, GUY)
        assert user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=AMY.id,
            message_id=message.id,
            emoji="➖",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=AMY,
        )
        assert not user_has_game(client, AMY)

    async def test_on_raw_reaction_add_minus_when_not_in_that_game(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        assert user_has_game(client, AMY)

        await client.on_message(MockMessage(GUY, channel, "!lfg ~chaos"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, GUY)
        assert user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=AMY.id,
            message_id=message.id,
            emoji="➖",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=AMY,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, AMY)

    async def test_game_cleanup_started(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert user_has_game(client, FRIEND)

        freezer.move_to(NOW + timedelta(days=3))
        await client.cleanup_started_games()

        assert not user_has_game(client, FRIEND)

    async def test_game_cleanup_expired(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        assert channel.last_sent_embed == game_embed_for(client, GUY, False)

        assert user_has_game(client, GUY)

        freezer.move_to(NOW + timedelta(days=3))
        await client.cleanup_expired_games()

        assert not user_has_game(client, GUY)
        assert GUY.last_sent_response == (
            f"My appologies <@{GUY.id}>,"
            " but I deleted your pending game due to server inactivity."
        )

        # TODO: Actually test that the embed was deleted correctly.

    async def test_game_cleanup_expired_after_left(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        assert channel.last_sent_embed == game_embed_for(client, GUY, False)

        assert user_has_game(client, GUY)

        client.mock_disconnect_user(GUY)

        freezer.move_to(NOW + timedelta(days=3))
        await client.cleanup_expired_games()

        assert not user_has_game(client, GUY)
        assert len(GUY.all_sent_calls) == 0

        # TODO: Actually test that the embed was deleted correctly.

    async def test_on_message_export_non_admin(self, client, channel_maker):
        channel = channel_maker.text()
        author = GUY
        await client.on_message(MockMessage(author, channel, "!export"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_export(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(JR, channel, "!lfg size:2 ~mtgo"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        game_one = all_games(client)[0]
        game_one_id = game_one["id"]
        game_one_at = game_one["created_at"]

        # game_two is pending, so it shouldn't show up in the csv export
        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))

        admin_author = an_admin()
        data = bytes(f"player1,player2\n{GUY.name},{FRIEND.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(admin_author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]

        await client.on_message(MockMessage(admin_author, channel, f"!begin {event_id}"))
        game_three = all_games(client)[-1]
        game_three_id = game_three["id"]
        game_three_at = game_three["created_at"]
        game_three_url = game_three["url"]

        await client.on_message(MockMessage(an_admin(), channel, "!export"))
        attachment = channel.all_sent_files[0]
        assert attachment.fp.read().decode() == (
            "id,size,status,system,channel,url,event_id,created_at,tags,message\n"
            f"{game_one_id},2,started,mtgo,#{channel.name},,,{game_one_at},,\n"
            f"{game_three_id},2,started,spelltable,,{game_three_url},{event_id},"
            f"{game_three_at},,\n"
        )

    async def test_on_message_play(self, client, channel_maker):
        channel = channel_maker.text()

        await client.on_message(MockMessage(ADAM, channel, "!play ~modern"))
        assert len(all_games(client)) == 1

        await client.on_message(MockMessage(ADAM, channel, "!play ~modern"))
        assert len(all_games(client)) == 1

        await client.on_message(MockMessage(JR, channel, "!play ~modern ~chaos"))
        assert len(all_games(client)) == 2

        await client.on_message(MockMessage(AMY, channel, "!play ~modern"))
        assert len(all_games(client)) == 2

        assert game_embed_for(client, ADAM, False) == game_embed_for(client, AMY, False)

        await client.on_message(MockMessage(TOM, channel, "!play ~modern ~chaos"))
        assert len(all_games(client)) == 2
        assert game_embed_for(client, JR, False) == game_embed_for(client, TOM, False)

        await client.on_message(MockMessage(JACOB, channel, "!play"))
        assert len(all_games(client)) == 3

        await client.on_message(MockMessage(GUY, channel, "!play ~modern ~no-ban-list"))
        assert len(all_games(client)) == 4

    async def test_on_message_play_full(self, client, channel_maker):
        channel = channel_maker.text()

        await client.on_message(MockMessage(JR, channel, "!play size:2"))
        assert len(all_games(client)) == 1

        await client.on_message(MockMessage(TOM, channel, "!play size:2"))
        assert len(all_games(client)) == 1
        assert game_embed_for(client, JR, True) == game_embed_for(client, TOM, True)

    async def test_on_message_join_none_found(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!join"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but I didn't find any games for you to join."
        )

    async def test_on_message_join(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JACOB, channel, "!join"))
        assert game_embed_for(client, AMY, False) == game_embed_for(client, JACOB, False)

    async def test_on_message_lfg_with_functional_tag(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg ~modern"))
        assert "1 more player" in channel.last_sent_embed["title"]

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~oathbreaker"))
        assert "3 more players" in channel.last_sent_embed["title"]

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~edh size: 3"))
        assert "2 more players" in channel.last_sent_embed["title"]

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg size:3 ~cedh"))
        assert "2 more players" in channel.last_sent_embed["title"]

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~king"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~emperor"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_join_up_with_someone(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg ~modern"))

        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!join {mentions_str}"
        await client.on_message(MockMessage(JACOB, channel, cmd, mentions=mentions))
        assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)

    async def test_on_message_spellbot_help(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot help"))
        assert len(channel.all_sent_calls) == 1
        assert len(author.all_sent_calls) >= 1

    async def test_on_message_queue_no_mentions(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!queue"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you need to mention at least one player."
        )

    async def test_on_message_queue_dm(self, client, channel_maker):
        author = an_admin()
        dm = channel_maker.dm()
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str}"
        await client.on_message(MockMessage(author, dm, cmd, mentions=mentions))
        assert author.last_sent_response == (
            f"Hello <@{author.id}>! That command only works in text channels."
        )

    async def test_on_message_queue_non_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_queue_admin(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.all_sent_responses[0] == f"I added <@{AMY.id}> to a queue."
        game = all_games(client)[0]
        game_id = game["id"]
        assert channel.all_sent_embeds[0] == {
            "color": 5914365,
            "description": "To join/leave this game, react with ➕/➖.",
            "fields": [{"inline": False, "name": "Players", "value": f"<@{AMY.id}>"}],
            "footer": {"text": f"SpellBot Reference #SB{game_id}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Waiting for 1 more player to join...**",
            "type": "rich",
        }

    async def test_on_message_queue_twice(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"The player <@{AMY.id}> was already in a game. I have removed them from"
            " that game. If you want to enter them into a queue, please run that"
            " command again to add them."
        )
        assert len(all_games(client)) == 1
        assert game_json_for(client, AMY) == None

    async def test_on_message_queue_till_ready(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()

        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))

        mentions = [JR]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))

        assert game_embed_for(client, AMY, True) == game_embed_for(client, JR, True)

    async def test_on_message_queue_till_ready_all(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()

        mentions = [AMY, JR]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))

        assert game_embed_for(client, AMY, True) == game_embed_for(client, JR, True)

    async def test_session_contextmanager(self, client, caplog):
        exception_thrown = False
        try:
            async with client.session() as session:
                session.execute("delete from nothing;")
                assert False
        except:
            exception_thrown = True

        assert exception_thrown
        assert "database error" in caplog.text

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_unhandled_exception(
        self, client, caplog, monkeypatch, channel_maker, channel_type
    ):
        channel = channel_maker.make(channel_type)

        @spellbot.command(allow_dm=True)
        def mock_help(session, prefix, params, message):
            raise RuntimeError("boom")

        monkeypatch.setattr(client, "help", mock_help)
        with pytest.raises(RuntimeError):
            await client.on_message(MockMessage(someone(), channel, "!help"))
        assert "unhandled exception" in caplog.text

    async def test_on_message_spellbot_links_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot links"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but please provide a links privacy setting."
        )

    async def test_on_message_spellbot_links_invalid(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot links foo"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but foo is not a valid setting."
            ' I was expecting either "private" or "public".'
        )

    async def test_on_message_spellbot_links(self, client, channel_maker):
        channel = channel_maker.text()

        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot links private"))
        assert channel.last_sent_response == (
            f"Right on, <@{author.id}>. From now on SpellTable links will be private."
        )

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!join ~legacy"))
        assert "http://" in game_embed_for(client, AMY, True, dm=True)["description"]
        assert "http://" not in game_embed_for(client, AMY, True, dm=False)["description"]

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_no_params(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_bad_param(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power bottom"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_neg_param(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power -5"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_high_param(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power 9000"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power 5"))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, your power level has been set to 5."
        )
        assert user_json_for(client, author)["power"] == 5
        await client.on_message(MockMessage(author, channel, "!power off"))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, your power level has been set to none."
        )
        assert user_json_for(client, author)["power"] == None

    async def test_on_message_lfg_with_power_similar(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!power 5"))
        await client.on_message(MockMessage(JR, channel, "!power 4"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        assert game_embed_for(client, AMY, False) == game_embed_for(client, JR, False)

        games = all_games(client)
        assert len(games) == 1
        game = games[0]
        assert game_embed_for(client, AMY, False) == {
            "color": 5914365,
            "description": "To join/leave this game, react with ➕/➖.",
            "fields": [
                {"inline": True, "name": "Average Power Level", "value": "4.5"},
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{AMY.id}> (Power: 5), <@{JR.id}> (Power: 4)",
                },
            ],
            "footer": {"text": f"SpellBot Reference #SB{game['id']}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Waiting for 2 more players to join...**",
            "type": "rich",
        }

    async def test_on_message_lfg_with_power_disjoint(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!power 5"))
        await client.on_message(MockMessage(JR, channel, "!power 10"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        assert game_embed_for(client, AMY, False) != game_embed_for(client, JR, False)
        assert len(all_games(client)) == 2

    async def test_on_message_lfg_with_power_vs_none(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!power 5"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        assert game_embed_for(client, AMY, False) != game_embed_for(client, JR, False)
        assert len(all_games(client)) == 2

    async def test_on_message_report_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!report"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, please provide the SpellBot game reference ID"
            " or SpellTable ID followed by your report."
        )

    async def test_on_message_report_one_param(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!report 1"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, please provide the SpellBot game reference ID"
            " or SpellTable ID followed by your report."
        )

    async def test_on_message_report_no_game(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!report 1 sup"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, I couldn't find a game with that ID."
        )

    async def test_on_message_report_bad_id(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!report 1=1 sup"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, I couldn't find a game with that ID."
        )

    async def test_on_message_report_too_long(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        msg = "foo " * 100
        await client.on_message(MockMessage(author, channel, f"!report 1 {msg}"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, that report was too long."
            " Please limit your report to less than 255 characters."
        )

    async def test_on_message_report_not_started(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        game = all_games(client)[0]
        game_id = game["id"]
        await client.on_message(MockMessage(author, channel, f"!report {game_id} foo"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but that game hasn't even started yet."
        )

    async def test_on_message_report_by_id(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))

        game = all_games(client)[0]
        game_id = game["id"]
        await client.on_message(MockMessage(AMY, channel, f"!report {game_id} sup"))
        assert channel.last_sent_response == f"Thanks for the report, <@{AMY.id}>!"
        await client.on_message(MockMessage(ADAM, channel, f"!report sb{game_id} word"))
        assert channel.last_sent_response == f"Thanks for the report, <@{ADAM.id}>!"
        await client.on_message(MockMessage(GUY, channel, f"!report SB{game_id} what"))
        assert channel.last_sent_response == f"Thanks for the report, <@{GUY.id}>!"

    async def test_on_message_report_by_url(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))

        game = all_games(client)[0]
        game_url = game["url"]
        game_id = game_url[game_url.rfind("/") + 1 :]
        await client.on_message(MockMessage(AMY, channel, f"!report {game_id} sup"))
        assert channel.last_sent_response == f"Thanks for the report, <@{AMY.id}>!"
        await client.on_message(MockMessage(ADAM, channel, f"!report a{game_id}z sup"))
        assert channel.last_sent_response == (
            f"Sorry <@{ADAM.id}>, I couldn't find a game with that ID."
        )

    async def test_on_message_spellbot_teams_not_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot teams one two"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_spellbot_teams_no_params(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot teams"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but please provide a list of team names."
        )

    async def test_on_message_spellbot_teams_too_few(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot teams cats"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but please give at least two team names."
        )

    async def test_on_message_spellbot_teams_dupes(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        cmd = "!spellbot teams cats cats dogs dogs cats"
        await client.on_message(MockMessage(author, channel, cmd))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've set the teams available on this server to:"
            " cats, dogs."
        )

    async def test_on_message_spellbot_teams(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()

        await client.on_message(MockMessage(author, channel, "!spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert "Teams" not in fields

        await client.on_message(MockMessage(author, channel, "!spellbot teams cats dogs"))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've set the teams available on this server to:"
            " cats, dogs."
        )

        await client.on_message(MockMessage(author, channel, "!spellbot teams ants cows"))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I've set the teams available on this server to:"
            " ants, cows."
        )

        await client.on_message(MockMessage(author, channel, "!spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Teams"] == "ants, cows"

    async def test_on_message_team_none(self, client, channel_maker):
        author = someone()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!team cats"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but there aren't any teams on this server."
        )

    async def test_on_message_team_not_set(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams cats dogs"))
        await client.on_message(MockMessage(author, channel, "!team"))
        assert channel.last_sent_response == (
            f"Hey <@{author.id}>, you are not currently a part of a team on this server."
        )

    async def test_on_message_team_yours(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams cats dogs"))
        await client.on_message(MockMessage(author, channel, "!team cAtS"))
        assert channel.last_sent_response == (
            f"Hey <@{author.id}>, you've joined the cats team!"
        )

        await client.on_message(MockMessage(author, channel, "!team"))
        assert channel.last_sent_response == (
            f"Hey <@{author.id}>, you are on the cats team."
        )

    async def test_on_message_team_not_found(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams cats dogs"))
        await client.on_message(MockMessage(author, channel, "!team frogs"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the teams available on this server are:"
            " cats, dogs."
        )

    async def test_on_message_team_gone(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams a b c d e"))
        await client.on_message(MockMessage(author, channel, "!team e"))

        async with client.session() as session:
            session.execute("delete from teams where name = 'e';")
            session.commit()

        await client.on_message(MockMessage(author, channel, "!team"))
        resp = channel.last_sent_response

        if resp == (
            f"Sorry <@{author.id}>, but the teams on this server have changed"
            " and your team no longer exists. Please choose a new team."
        ):
            pass  # sqlite
        elif resp == (
            f"Hey <@{author.id}>, you are not currently a part of a team on this server."
        ):
            # databases where cascade works

            # Since this string won't get exercised,
            # we have to call it or else the meta test will fail.
            from .test_meta import S_SPY

            S_SPY("team_gone", reply="")
        else:
            assert False

    async def test_on_message_team(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams cats dogs"))
        await client.on_message(MockMessage(author, channel, "!team dogs"))
        assert channel.last_sent_response == (
            f"Hey <@{author.id}>, you've joined the dogs team!"
        )
        await client.on_message(MockMessage(author, channel, "!team cats"))
        assert channel.last_sent_response == (
            f"Hey <@{author.id}>, you've joined the cats team!"
        )
        await client.on_message(MockMessage(author, channel, "!team dogs"))
        assert channel.last_sent_response == (
            f"Hey <@{author.id}>, you've joined the dogs team!"
        )

    async def test_report_points(self):
        # FIXME: For now I'm not adding tests for the special CFB event code.
        from .test_meta import S_SPY

        S_SPY("report_wrong", reply="")
        S_SPY("report_incomplete", reply="")
        S_SPY("points_team", reply="", team="", points="")
        S_SPY("points", reply="", points="")
        assert 1 == 1

    async def test_paginate(self):
        def subject(text):
            return [page for page in spellbot.paginate(text)]

        assert subject("") == [""]
        assert subject("four") == ["four"]

        with open(Path(TEST_DATA_ROOT) / "ipsum_2011.txt") as f:
            text = f.read()
            pages = subject(text)
            assert len(pages) == 2
            assert all(len(page) <= 2000 for page in pages)
            assert pages == [text[0:1937], text[1937:]]

        with open(Path(TEST_DATA_ROOT) / "aaa_2001.txt") as f:
            text = f.read()
            pages = subject(text)
            assert len(pages) == 2
            assert all(len(page) <= 2000 for page in pages)
            assert pages == [text[0:2000], text[2000:]]

        with open(Path(TEST_DATA_ROOT) / "quotes.txt") as f:
            text = f.read()
            pages = subject(text)
            assert len(pages) == 2
            assert all(len(page) <= 2000 for page in pages)
            assert pages == [text[0:2000], f"> {text[2000:]}"]
