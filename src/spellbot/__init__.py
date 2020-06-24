import asyncio
import inspect
import logging
from os import getenv
from pathlib import Path

import click
import discord
import hupper

from spellbot._version import __version__
from spellbot.assets import ASSET_FILES, s
from spellbot.data import Data

# Application Paths
RUNTIME_ROOT = Path(".")
SCRIPTS_DIR = RUNTIME_ROOT / "scripts"
DB_DIR = RUNTIME_ROOT / "db"
DEFAULT_DB_URL = f"sqlite:///{DB_DIR}/spellbot.db"
TMP_DIR = RUNTIME_ROOT / "tmp"
MIGRATIONS_DIR = SCRIPTS_DIR / "migrations"

# Application Settings
ADMIN_ROLE = "SpellBot Admin"


class Direct:
    """Use this to indicate that a command should send a DM."""

    def __init__(self, response):
        self.response = response


def discord_user_from_name(channel, name):
    """Returns the discord user from the given channel and name."""
    if name is None:
        return None
    lname = name.lower()
    if hasattr(channel, "members"):  # channels
        members = channel.members
        return next(filter(lambda member: lname in str(member).lower(), members), None)
    else:  # direct messages
        recipient = channel.recipient
        rvalue = recipient if name in str(recipient).lower() else None
        return rvalue


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


def discord_user_name(channel, name_or_id):
    """Returns the discord user name from the given channel and name or id."""
    if not name_or_id:
        return None
    user = (
        discord_user_from_id(channel, name_or_id)
        if isinstance(name_or_id, int) or name_or_id.isdigit()
        else discord_user_from_name(channel, name_or_id)
    )
    return str(user) if user else None


def discord_user_id(channel, name):
    """Returns the discord user id name from the given channel and name."""
    if not name:
        return None
    user = discord_user_from_name(channel, name)
    return user.id if user else None


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


def command(f):
    """Decorator for bot command methods."""
    f.is_command = True
    return f


class SpellBot(discord.Client):
    """Discord SpellTable Bot"""

    def __init__(
        self, token="", db_url=DEFAULT_DB_URL, log_level=logging.ERROR, metrics=False,
    ):
        logging.basicConfig(level=log_level)
        loop = asyncio.get_event_loop()
        super().__init__(loop=loop)
        self.token = token

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

    def ensure_user_exists(self, user):
        """Ensures that the user row exists for the given discord user."""
        pass
        # if not self.session.query(User).get(user.id):
        #     self.session.add(User(author=user.id))

    def paginate(self, text):
        """Discord responses must be 2000 characters of less; paginate breaks them up."""
        breakpoints = ["\n", ".", ",", "-"]
        remaining = text
        while len(remaining) > 2000:
            breakpoint = 1999

            for char in breakpoints:
                index = remaining.rfind(char, 1800, 1999)
                if index != -1:
                    breakpoint = index
                    break

            message = remaining[0 : breakpoint + 1]
            yield message
            remaining = remaining[breakpoint + 1 :]
            last_line_end = message.rfind("\n")
            if last_line_end != -1 and len(message) > last_line_end + 1:
                last_line_start = last_line_end + 1
            else:
                last_line_start = 0
            if message[last_line_start] == ">":
                remaining = f"> {remaining}"

        yield remaining

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
            logging.debug("%s (author=%s, params=%s)", command, message.author, params)
            method = getattr(self, command)
            async with message.channel.typing():
                self.session = self.data.Session()
                try:
                    response, attachment = method(message.channel, message.author, params)
                    self.session.commit()
                except:
                    self.session.rollback()
                    raise
                finally:
                    self.session.close()
            if isinstance(response, Direct):
                send_direct = True
                response = response.response
            else:
                send_direct = False
            if not isinstance(response, list):
                response = [response]
            last_reply_index = len(response) - 1
            for n, reply in enumerate(response):
                if isinstance(reply, str):
                    pages = list(self.paginate(reply))
                    last_page_index = len(pages) - 1
                    for i, page in enumerate(pages):
                        file = (
                            attachment
                            if attachment is not None
                            and i == last_page_index
                            and n == last_reply_index
                            else None
                        )
                        if send_direct:
                            await message.author.send(page, file=file)
                        else:
                            await message.channel.send(page, file=file)
                elif isinstance(reply, discord.embeds.Embed):
                    file = (
                        attachment
                        if attachment is not None and n == last_reply_index
                        else None
                    )
                    if send_direct:
                        await message.author.send(embed=reply, file=file)
                    else:
                        await message.channel.send(embed=reply, file=file)
                else:
                    raise RuntimeError("non-string non-embed reply not supported")

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
    #     @command
    #     def command_name(self, channel, author, params)
    #
    # - `channel` is the Discord channel where the command message was sent.
    # - `author` is the Discord author who sent the command.
    # - `params` are any space delimitered parameters also sent with the command.
    #
    # The return value for a command method can be `(string, discord.File)` where the
    # string is the response message the bot should send to the channel and the file
    # object is an attachment to send with the message. For no attachment, use `None`.
    #
    # You can also return `(embed, discord.File)` to respond with an embed (plus the
    # optional attachment as well if so desired).
    #
    # And finally you can also respond with a list if you want the bot to make multiple
    # replies. This works with both embeds and strings. For example:
    #
    #     return ["send", "multiple", "replies"], None
    #
    # Would trigger the bot to send three messages to the channel with no attachment.
    #
    # The docstring used for the command method will be automatically used as the help
    # message for the command. To document commands with parameters use a @ to delimit
    # the help message from the parameter documentation. For example:
    #
    #     """This is the help message for your command. @ [and] [these] [are] [params]"""
    #
    # A [parameter] is optional whereas a <parameter> is required.

    @command
    def help(self, channel, author, params):
        """
        Shows this help screen.
        """
        usage = "__**SpellBot Help!**__\n"
        for command in self.commands:
            method = getattr(self, command)
            doc = method.__doc__.split("@")
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
        return Direct(usage), None

    @command
    def hello(self, channel, author, params):
        """
        Says hello.
        """
        return "Hello!", None

    @command
    def about(self, channel, author, params):
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
        author = "[Amy](https://github.com/lexicalunit)"
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
        return embed, None


def get_db_url(database_env, fallback):  # pragma: no cover
    """Returns the database url from the environment or else the given fallback."""
    value = getenv(database_env, fallback)
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

    # We have to make sure that application directories exist
    # before we try to create we can run any of the migrations.
    ensure_application_directories_exist()

    client = SpellBot(
        token=getenv("SPELLBOT_TOKEN", None),
        db_url=database_url,
        log_level="DEBUG" if verbose else log_level,
    )

    if dev:
        reloader = hupper.start_reloader("spellbot.main")
        reloader.watch_files(ASSET_FILES)

    client.run()


if __name__ == "__main__":
    main()
