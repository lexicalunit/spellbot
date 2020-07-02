import asyncio
import inspect
import logging
from functools import wraps
from os import getenv
from pathlib import Path

import click
import discord
import hupper
import requests

from spellbot._version import __version__
from spellbot.assets import ASSET_FILES, s
from spellbot.data import Data, Tag, User

# Application Paths
RUNTIME_ROOT = Path(".")
SCRIPTS_DIR = RUNTIME_ROOT / "scripts"
DB_DIR = RUNTIME_ROOT / "db"
DEFAULT_DB_URL = f"sqlite:///{DB_DIR}/spellbot.db"
TMP_DIR = RUNTIME_ROOT / "tmp"
MIGRATIONS_DIR = SCRIPTS_DIR / "migrations"

# Application Settings
ADMIN_ROLE = "SpellBot Admin"
CREATE_ENDPOINT = "https://us-central1-magic-night-30324.cloudfunctions.net/createGame"


def discord_user_from_id(channel, user_id):
    """Returns the discord user from the given channel and user id."""
    if user_id is None:
        return None
    iid = int(user_id)
    if hasattr(channel, "members"):  # channels
        members = channel.members
        return next(filter(lambda member: iid == member.id, members), None)
    else:  # direct messages
        recipient = channel.recipient
        return recipient if recipient.id == user_id else None


def is_admin(channel, user_or_member):
    """Checks to see if given user or member has the admin role on this server."""
    member = (
        user_or_member
        if hasattr(user_or_member, "roles")  # members have a roles property
        else channel.guild.get_member(user_or_member.id)  # but users don't
    )
    return any(role.name == ADMIN_ROLE for role in member.roles) if member else False


def ensure_application_directories_exist():
    """Idempotent function to make sure needed application directories are there."""
    TMP_DIR.mkdir(exist_ok=True)
    DB_DIR.mkdir(exist_ok=True)


def command(allow_dm=True):
    """Decorator for bot command methods."""

    def callable(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            return await func(*args, **kwargs)

        wrapped.is_command = True
        wrapped.allow_dm = allow_dm
        return wrapped

    return callable


class SpellBot(discord.Client):
    """Discord SpellTable Bot"""

    def __init__(
        self,
        token="",
        auth="",
        db_url=DEFAULT_DB_URL,
        log_level=logging.ERROR,
        metrics=False,
    ):
        logging.basicConfig(level=log_level)
        loop = asyncio.get_event_loop()
        super().__init__(loop=loop)
        self.token = token
        self.auth = auth

        # During the processing of a command there will be valid SQLAlchemy session
        # object available for use, commits and rollbacks are handled automatically.
        self.session = None

        # We have to make sure that DB_DIR exists before we try to create
        # the database as part of instantiating the Data object.
        ensure_application_directories_exist()
        self.data = Data(db_url)

        # build a list of commands supported by this bot by fetching @command methods
        members = inspect.getmembers(self, predicate=inspect.ismethod)
        self._commands = [
            member[0]
            for member in members
            if hasattr(member[1], "is_command") and member[1].is_command
        ]

    def run(self):  # pragma: no cover
        super().run(self.token)

    def create_game(self):  # pragma: no cover
        headers = {"user-agent": f"spellbot/{__version__}", "key": self.auth}
        r = requests.post(CREATE_ENDPOINT, headers=headers)
        return r.json()["gameUrl"]

    def ensure_user_exists(self, user):
        """Ensures that the user row exists for the given discord user."""
        db_user = self.session.query(User).filter(User.xid == user.id).first()
        if not db_user:
            db_user = User(xid=user.id)
            self.session.add(db_user)
        return db_user

    @property
    def commands(self):
        """Returns a list of commands supported by this bot."""
        return self._commands

    async def process(self, message):
        """Process a command message."""
        tokens = message.content.split(" ")
        request, params = tokens[0].lstrip("!").lower(), tokens[1:]
        params = list(filter(None, params))  # ignore any empty string parameters
        if not request:
            return
        matching = [command for command in self.commands if command.startswith(request)]
        if not matching:
            await message.channel.send(s("not_a_command", request=request), file=None)
            return
        if len(matching) > 1 and request not in matching:
            possible = ", ".join(f"!{m}" for m in matching)
            await message.channel.send(s("did_you_mean", possible=possible), file=None)
        else:
            command = request if request in matching else matching[0]
            method = getattr(self, command)
            if not method.allow_dm and str(message.channel.type) == "private":
                return
            mentions = message.mentions if message.channel.type != "private" else []
            logging.debug(
                "%s (channel=%s, author=%s, mentions=%s, params=%s)",
                command,
                message.channel,
                message.author,
                mentions,
                params,
            )
            self.session = self.data.Session()
            try:
                await method(message.channel, message.author, mentions, params)
                self.session.commit()
            except:
                self.session.rollback()
                raise
            finally:
                self.session.close()

    ##############################
    # Discord Client Behavior
    ##############################

    async def on_message(self, message):
        """Behavior when the client gets a message from Discord."""
        # don't respond to any bots
        if message.author.bot:
            return

        private = str(message.channel.type) == "private"

        # only respond in text channels and to direct messages
        if not private and str(message.channel.type) != "text":
            return

        # don't respond to yourself
        if message.author.id == self.user.id:
            return

        # only respond to command-like messages
        if not message.content.startswith("!"):
            return

        if not private:
            # check for admin authorized channels on this server
            guild_id = message.channel.guild.id
            rows = self.data.conn.execute(
                f"SELECT * FROM authorized_channels WHERE guild = {guild_id};"
            )
            authorized_channels = set(row["name"] for row in rows)
            if authorized_channels and message.channel.name not in authorized_channels:
                return

        await self.process(message)

    async def on_ready(self):
        """Behavior when the client has successfully connected to Discord."""
        logging.debug("logged in as %s", self.user)

    ##############################
    # Bot Command Functions
    ##############################

    # Any method of this class with a name that is decorated by @command is detected as a
    # bot command. These methods should have a signature like:
    #
    #     @command(allow_dm=True)
    #     def command_name(self, channel, author,mentions, params)
    #
    # - `allow_dm` indicates if the command is allowed to be used in direct messages.
    # - `channel` is the Discord channel where the command message was sent.
    # - `author` is the Discord author who sent the command.
    # - `params` are any space delimitered parameters also sent with the command.
    #
    # The docstring used for the command method will be automatically used as the help
    # message for the command. To document commands with parameters use a & to delimit
    # the help message from the parameter documentation. For example:
    #
    #     """This is the help message for your command. & <and> [these] [are] [params]"""
    #
    # Where [foo] indicates foo is optional and <bar> indicates bar is required.

    @command(allow_dm=True)
    async def help(self, channel, author, mentions, params):
        """
        Shows this help screen.
        """
        usage = "__**SpellBot Usage**__\n"
        for command in self.commands:
            method = getattr(self, command)
            doc = method.__doc__.split("&")
            use, params = doc[0], ", ".join([param.strip() for param in doc[1:]])
            use = inspect.cleandoc(use)
            use = use.replace("\n", " ")

            title = f"**!{command}**"
            if params:
                title = f"{title} _{params}_"
            usage += f"\n{title}"
            usage += f"\n>  {use}"
            usage += "\n"
        usage += "\n_SpellBot created by amy@lexicalunit.com_"
        await author.send(usage, file=None)

    @command(allow_dm=True)
    async def hello(self, channel, author, mentions, params):
        """
        Says hello.
        """
        await channel.send("Hello!")

    @command(allow_dm=True)
    async def about(self, channel, author, mentions, params):
        """
        Get information about SpellBot.
        """
        embed = discord.Embed(title="SpellBot")
        thumb = (
            "https://raw.githubusercontent.com/lexicalunit/spellbot/master/spellbot.png"
        )
        embed.set_thumbnail(url=thumb)
        version = f"[{__version__}](https://pypi.org/project/spellbot/{__version__}/)"
        embed.add_field(name="Version", value=version)
        embed.add_field(
            name="Package", value="[PyPI](https://pypi.org/project/spellbot/)"
        )
        author = "[@lexicalunit](https://github.com/lexicalunit)"
        embed.add_field(name="Author", value=author)
        embed.description = (
            "_A Discord bot for SpellTable._\n"
            "\n"
            "Use the command `!help` for usage details. Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
        )
        embed.url = "https://github.com/lexicalunit/spellbot"
        embed.set_footer(text="MIT © amy@lexicalunit et al")
        embed.color = discord.Color(0x5A3EFD)
        await channel.send(embed=embed, file=None)

    @command(allow_dm=False)
    async def queue(self, channel, author, mentions, params):
        """
        Enter the queue for a game on SpellTable.

        You can get in the queue with a friend by including them in the command with as
        many @ mentions as you want. You can also choose the number of players by using
        `size:2` for a two player game, for example. The default number of players is 4.

        You can also give a list of tags and you will only be matched against users who
        have the same tags as you. For example, if you want to enter into a cEDH queue
        you could try `!queue cEDH`. Check with your server for supported tags.
        & [@mention-1] [@mention-2] [...] [size:N] [tag-1] [tag-2] [...]
        """
        user = self.ensure_user_exists(author)
        if user.waiting:
            return await author.send(s("queue_already"))

        def to_int(s):
            try:
                return int(s)
            except ValueError:
                return None

        size = 4
        for param in params:
            if param.startswith("size:"):
                size = to_int(param.replace("size:", ""))

        if not size or not (1 < size < 5):
            return await author.send(s("queue_size_bad"))

        if len(mentions) >= size:
            return await author.send(s("queue_too_many"))

        mentioned_users = []
        for mentioned in mentions:
            mentioned_user = self.ensure_user_exists(mentioned)
            if mentioned_user.waiting:
                return await author.send(s("queue_mention_already", user=mentioned))
            mentioned_users.append(mentioned_user)

        tags = []
        tag_names = [
            param
            for param in params
            if not param.startswith("size:") and not param.startswith("@")
        ]
        if not tag_names:
            tag_names = ["default"]
        for tag_name in tag_names:
            tag = self.session.query(Tag).filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                self.session.add(tag)
            tags.append(tag)

        user.enqueue(
            size=size, guild_xid=channel.guild.id, include=mentioned_users, tags=tags
        )
        self.session.commit()

        if len(user.game.users) == size:
            game_url = self.create_game()
            for player in user.game.users:
                discord_user = discord_user_from_id(channel, player.xid)
                await discord_user.send(s("queue_ready", url=game_url))
            self.session.delete(user.game)
        else:
            for player in user.game.users:
                discord_user = discord_user_from_id(channel, player.xid)
                await discord_user.send(s("queue"))

    @command(allow_dm=True)
    async def leave(self, channel, author, mentions, params):
        """
        Leave your place in the queue.
        """
        user = self.ensure_user_exists(author)
        if not user.waiting:
            return await author.send(s("leave_already"))

        user.dequeue()
        await author.send(s("leave"))


def get_db_url(database_env, fallback):  # pragma: no cover
    """Returns the database url from the environment or else the given fallback."""
    value = getenv(database_env, fallback)
    return value or fallback


def get_log_level(fallback):  # pragma: no cover
    """Returns the log level from the environment or else the given gallback."""
    value = getenv("SPELLTABLE_LOG_LEVEL", fallback)
    return value or fallback


@click.command()
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]),
    default="ERROR",
)
@click.option("-v", "--verbose", count=True, help="Sets log level to DEBUG.")
@click.option(
    "-d",
    "--database-url",
    default=DEFAULT_DB_URL,
    help=(
        "Database url connection string; "
        "you can also set this via the SPELLBOT_DB_URL environment variable."
    ),
)
@click.option(
    "--database-env",
    default="SPELLBOT_DB_URL",
    help=(
        "By default SpellBot look in the environment variable SPELLBOT_DB_URL for the "
        "database connection string. If you need it to look in a different variable "
        "you can set it with this option. For example Heroku uses DATABASE_URL."
    ),
)
@click.version_option(version=__version__)
@click.option(
    "--dev",
    default=False,
    is_flag=True,
    help="Development mode, automatically reload bot when source changes",
)
def main(
    log_level, verbose, database_url, database_env, dev,
):  # pragma: no cover
    database_url = get_db_url(database_env, database_url)
    log_level = get_log_level(log_level)

    # We have to make sure that application directories exist
    # before we try to create we can run any of the migrations.
    ensure_application_directories_exist()

    # TODO: Check that SPELLBOT_TOKEN and SPELLTABLE_AUTH are properly set.
    # TODO: Add env var to set log level.

    client = SpellBot(
        token=getenv("SPELLBOT_TOKEN", None),
        auth=getenv("SPELLTABLE_AUTH", None),
        db_url=database_url,
        log_level="DEBUG" if verbose else log_level,
    )

    if dev:
        reloader = hupper.start_reloader("spellbot.main")
        reloader.watch_files(ASSET_FILES)

    client.run()


if __name__ == "__main__":
    main()
