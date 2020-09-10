import asyncio
import csv
import inspect
import logging
import re
import sys
from asyncio.events import AbstractEventLoop
from contextlib import asynccontextmanager, redirect_stdout
from datetime import datetime, timedelta
from functools import wraps
from io import StringIO
from os import getenv
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Iterator,
    List,
    Optional,
    Set,
    Union,
    cast,
)
from uuid import uuid4

import click
import coloredlogs  # type: ignore
import discord
import discord.errors
import hupper  # type: ignore
import requests
from aiohttp import web
from discord.channel import TextChannel
from dotenv import load_dotenv
from sqlalchemy import exc
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import text

from spellbot._version import __version__
from spellbot.assets import ASSET_FILES, s
from spellbot.constants import (
    ADMIN_ROLE,
    CREATE_ENDPOINT,
    DEFAULT_GAME_SIZE,
    INVITE_LINK,
    THUMB_URL,
    VOTE_LINK,
)
from spellbot.data import (
    Channel,
    Data,
    Event,
    Game,
    Report,
    Server,
    Tag,
    Team,
    User,
    UserPoints,
    UserTeam,
)
from spellbot.operations import (
    safe_clear_reactions,
    safe_delete_message,
    safe_edit_message,
    safe_fetch_channel,
    safe_fetch_message,
    safe_fetch_user,
    safe_react_error,
    safe_react_ok,
    safe_remove_reaction,
)

load_dotenv()

# Application Paths
RUNTIME_ROOT = Path(".")
SCRIPTS_DIR = RUNTIME_ROOT / "scripts"
DB_DIR = RUNTIME_ROOT / "db"
TMP_DIR = RUNTIME_ROOT / "tmp"
MIGRATIONS_DIR = SCRIPTS_DIR / "migrations"

DEFAULT_DB_URL = f"sqlite:///{DB_DIR}/spellbot.db"
DEFAULT_PORT = 5020
DEFAULT_HOST = "localhost"

logger = logging.getLogger(__name__)


def to_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except ValueError:
        return None


def parse_opts(params: List[str]) -> dict:
    tags: List[str] = []
    first_pass: List[str] = []
    second_pass: List[str] = []
    size: Optional[int] = DEFAULT_GAME_SIZE
    msg: Optional[str] = None
    skip_next: bool = False
    system: str = "spelltable"

    TWO_PLAYER_FORMATS = [
        "standard",
        "modern",
        "pioneer",
        "legacy",
        "vintage",
        "pauper",
        "peasant",
        "frontier",
        "cube",
    ]
    FOUR_PLAYER_FORMATS = [
        "commander",
        "edh",
        "cedh",
        "oathbreaker",
        "2hg",
        "two-headed-giant",
        "2-headed-giant",
    ]
    FIVE_PLAYER_FORMATS = ["king"]
    SIX_PLAYER_FORMATS = ["emperor"]

    size_set = False
    for i, param in enumerate(params):
        if skip_next:
            skip_next = False
            continue

        if param.lower() in ["~mtgo", "~modo"]:
            system = "mtgo"
        elif param.lower() in ["~arena", "~mtga"]:
            system = "arena"
        elif param.startswith("~"):
            tag = param[1:].lower()
            tags.append(tag)
            if not size_set and tag in TWO_PLAYER_FORMATS:
                size = 2
            elif not size_set and tag in FOUR_PLAYER_FORMATS:
                size = 4
            elif not size_set and tag in FIVE_PLAYER_FORMATS:
                size = 5
            elif not size_set and tag in SIX_PLAYER_FORMATS:
                size = 6
        elif param.lower().startswith("size:"):
            size_set = True
            rest = param[5:]
            if rest:
                if rest.isdigit():
                    size = int(rest)
                else:
                    size = None
            else:
                if params[i + 1].isdigit():
                    size = int(params[i + 1])
                    skip_next = True
                else:
                    size = None
        else:
            first_pass.append(param)

    for i, param in enumerate(first_pass):
        if param.lower().startswith("msg:"):
            rest = param[4:]
            if rest:
                msg = " ".join([rest] + first_pass[i + 1 :])
            else:
                msg = " ".join(first_pass[i + 1 :])
            break
        else:
            second_pass.append(param)

    return {
        "message": msg,
        "params": second_pass,
        "size": size,
        "system": system,
        "tags": tags,
    }


def post_link(server_xid: int, channel_xid: int, message_xid: int) -> str:
    return f"https://discordapp.com/channels/{server_xid}/{channel_xid}/{message_xid}"


def is_admin(
    channel: TextChannel, user_or_member: Union[discord.User, discord.Member]
) -> bool:
    """Checks to see if given user or member has the admin role on this server."""
    member = (
        user_or_member
        if hasattr(user_or_member, "roles")
        else channel.guild.get_member(cast(discord.User, user_or_member).id)
    )
    roles = cast(List[discord.Role], cast(discord.Member, member).roles)
    return any(role.name == ADMIN_ROLE for role in roles) if member else False


async def check_is_admin(message: discord.Message) -> bool:
    """Checks if author of message is admin, alert the channel if they are not."""
    if not is_admin(message.channel, message.author):
        user_xid = cast(discord.User, message.author).id
        await message.channel.send(s("not_admin", reply=f"<@{user_xid}>"))
        return False
    return True


def ensure_application_directories_exist() -> None:
    """Idempotent function to make sure needed application directories are there."""
    TMP_DIR.mkdir(exist_ok=True)
    DB_DIR.mkdir(exist_ok=True)


def paginate(text: str) -> Iterator[str]:
    """Discord responses must be 2000 characters of less; paginate breaks them up."""
    breakpoints = ["\n", ".", ",", "-"]
    remaining = text
    while len(remaining) > 2000:
        bp_pos = 1999

        for char in breakpoints:
            index = remaining.rfind(char, 1800, 1999)
            if index != -1:
                bp_pos = index
                break

        message = remaining[0 : bp_pos + 1]
        yield message.rstrip(" >\n")
        remaining = remaining[bp_pos + 1 :]
        last_line_end = message.rfind("\n")
        if last_line_end != -1 and len(message) > last_line_end + 1:
            last_line_start = last_line_end + 1
        else:
            last_line_start = 0
        if message[last_line_start] == ">":
            remaining = f"> {remaining}"

    yield remaining


def command(
    allow_dm: bool = True,
    admin_only: bool = False,
    help_group: Optional[str] = None,
) -> Callable:
    """Decorator for bot command methods."""

    def command_callable(func: Callable):
        @wraps(func)
        async def wrapped(*args, **kwargs) -> Any:
            return await func(*args, **kwargs)

        cast(Any, wrapped).is_command = True
        cast(Any, wrapped).allow_dm = allow_dm
        cast(Any, wrapped).admin_only = admin_only
        cast(Any, wrapped).help_group = help_group
        return wrapped

    return command_callable


class SpellBot(discord.Client):
    """Discord SpellTable Bot"""

    def __init__(
        self,
        token: Optional[str] = None,
        auth: Optional[str] = None,
        db_url: str = DEFAULT_DB_URL,
        log_level: Union[int, str] = logging.ERROR,
        mock_games: bool = False,
        loop: AbstractEventLoop = None,
    ):
        coloredlogs.install(
            level=log_level,
            fmt="[%(asctime)s][%(name)s][%(levelname)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            field_styles={
                "asctime": {"color": "cyan"},
                "hostname": {"color": "magenta"},
                "levelname": {"bold": True, "color": "black"},
                "name": {"color": "blue"},
                "programname": {"color": "cyan"},
                "username": {"color": "yellow"},
            },
            level_styles={
                "debug": {"color": "magenta"},
                "info": {"color": "green"},
                "warning": {"color": "yellow"},
                "error": {"color": "red"},
                "critical": {"color": "red"},
            },
        )
        if not loop:
            loop = asyncio.get_event_loop()
        super().__init__(loop=loop)
        self.token = token or ""
        self.auth = auth or ""
        self.mock_games = mock_games

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

        self._begin_background_tasks(loop)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Session, None]:
        session = self.data.Session()
        try:
            yield session
        except exc.SQLAlchemyError as e:
            logger.exception("database error: %s", e)
            session.rollback()
            raise
        finally:
            session.close()

    def _begin_background_tasks(
        self, loop: asyncio.AbstractEventLoop
    ) -> None:  # pragma: no cover
        """Start up any periodic background tasks."""
        self.cleanup_expired_games_task(loop)

        # TODO: Make this manually triggered.
        # self.cleanup_started_games_task(loop)

    def cleanup_expired_games_task(
        self, loop: asyncio.AbstractEventLoop
    ) -> None:  # pragma: no cover
        """Starts a task that culls old games."""
        THIRTY_SECONDS = 30

        async def task() -> None:
            while True:
                await asyncio.sleep(THIRTY_SECONDS)
                await self.cleanup_expired_games()

        loop.create_task(task())

    async def cleanup_expired_games(self) -> None:
        """Culls games older than the given window of minutes."""
        async with self.session() as session:
            expired = Game.expired(session)
            for game in expired:
                await self.try_to_delete_message(game)
                for user in game.users:
                    discord_user = await safe_fetch_user(self, user.xid)
                    if discord_user:
                        await discord_user.send(
                            s(
                                "expired",
                                reply=f"<@{discord_user.id}>",
                                window=game.server.expire,
                            )
                        )
                    user.game_id = None
                game.tags = []  # cascade delete tag associations
                session.delete(game)
            session.commit()

    def cleanup_started_games_task(
        self, loop: asyncio.AbstractEventLoop
    ) -> None:  # pragma: no cover
        """Starts a task that culls old games."""
        FOUR_HOURS = 14400

        async def task() -> None:
            while True:
                await asyncio.sleep(FOUR_HOURS)
                await self.cleanup_started_games()

        loop.create_task(task())

    async def cleanup_started_games(self) -> None:
        """Culls games older than the given window of minutes."""
        async with self.session() as session:
            games = session.query(Game).filter(Game.status == "started").all()
            for game in games:
                game.tags = []  # cascade delete tag associations
                session.delete(game)
            session.commit()

    @property
    def commands(self) -> List[str]:
        """Returns a list of commands supported by this bot."""
        return self._commands

    def run(self) -> None:  # pragma: no cover
        super().run(self.token)

    def create_game(self) -> str:  # pragma: no cover
        if self.mock_games:
            return f"http://exmaple.com/game/{uuid4()}"

        headers = {"user-agent": f"spellbot/{__version__}", "key": self.auth}
        r = requests.post(CREATE_ENDPOINT, headers=headers)
        return cast(str, r.json()["gameUrl"])

    def ensure_user_exists(
        self, session: Session, user: Union[discord.User, discord.Member]
    ) -> User:
        """Ensures that the user row exists for the given discord user."""
        user_xid = cast(Any, user).id  # typing doesn't recognize that id exists
        db_user = session.query(User).filter(User.xid == user_xid).one_or_none()
        if not db_user:
            db_user = User(xid=user_xid, game_id=None, cached_name=cast(Any, user).name)
            session.add(db_user)
        else:
            # try to keep this relatively up to date
            db_user.name = cast(Any, user).name
        session.commit()
        return cast(User, db_user)

    def ensure_server_exists(self, session: Session, guild_xid: int) -> Server:
        """Ensures that the server row exists for the given discord guild id."""
        server = session.query(Server).filter(Server.guild_xid == guild_xid).one_or_none()
        if not server:
            server = Server(guild_xid=guild_xid)
            session.add(server)
            session.commit()
        return cast(Server, server)

    async def try_to_delete_message(self, game: Game) -> None:
        """Attempts to remove a ✋ from the given game message for the given user."""
        if not game.channel_xid:
            return

        chan = await safe_fetch_channel(self, game.channel_xid, game.guild_xid)
        if not chan:
            return

        if not game.message_xid:
            return

        post = await safe_fetch_message(chan, game.message_xid, game.guild_xid)
        if not post:
            return

        await safe_delete_message(post)

    async def try_to_update_game(self, game) -> None:
        """Attempts to update the embed for a game."""
        if not game.channel_xid or not game.message_xid:
            return

        chan = await safe_fetch_channel(self, game.channel_xid, game.guild_xid)
        if not chan:
            return

        post = await safe_fetch_message(chan, game.message_xid, game.guild_xid)
        if not post:
            return

        await post.edit(embed=game.to_embed())

    async def process(self, message: discord.Message, prefix: str) -> None:
        """Process a command message."""
        tokens = message.content.split(" ")
        request, params = tokens[0].lstrip(prefix).lower(), tokens[1:]
        params = list(filter(None, params))  # ignore any empty string parameters
        if not request:
            return

        # Special handling for `!powerX`: Tease apart the command request from parameter.
        if request.startswith("power") and len(request) > 5 and request[5:].isdigit():
            params.insert(0, request[5:])
            request = "power"

        matching = [command for command in self.commands if command.startswith(request)]
        if not matching:
            await message.channel.send(
                s(
                    "not_a_command",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    request=request,
                    prefix=prefix,
                )
            )
            return
        if len(matching) > 1 and request not in matching:
            possible = ", ".join(f"{prefix}{m}" for m in matching)
            await message.channel.send(
                s(
                    "did_you_mean",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    possible=possible,
                )
            )
            return

        command = request if request in matching else matching[0]
        method = getattr(self, command)
        if not method.allow_dm and str(message.channel.type) == "private":
            await message.author.send(
                s("no_dm", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            return
        if method.admin_only and not await check_is_admin(message):
            return
        logger.debug("%s%s (params=%s, message=%s)", prefix, command, params, message)
        async with self.session() as session:
            await method(session, prefix, params, message)
            return

    ##############################
    # Discord Client Behavior
    ##############################

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Behavior when the client gets a new reaction on a Discord message."""
        emoji = str(payload.emoji)
        if emoji not in ["✋", "🚫"]:
            return

        channel = await safe_fetch_channel(
            self, payload.channel_id, payload.guild_id or 0
        )
        if not channel or str(channel.type) != "text":
            return

        # From the docs: payload.member is available if `event_type` is `REACTION_ADD`.
        author = cast(discord.User, payload.member)
        if author.bot:
            return

        message = await safe_fetch_message(
            channel, payload.message_id, payload.guild_id or 0
        )
        if not message:
            return

        async with self.session() as session:
            assert payload.guild_id is not None
            server = self.ensure_server_exists(session, payload.guild_id)

            if not server.bot_allowed_in(channel.id):
                return

            game = (
                session.query(Game).filter(Game.message_xid == message.id).one_or_none()
            )
            if not game or game.status != "pending":
                return  # this isn't a post relating to a pending game, just ignore it

            user = self.ensure_user_exists(session, author)

            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=server.expire)

            await safe_remove_reaction(message, emoji, author)

            if emoji == "✋":
                if any(user.xid == game_user.xid for game_user in game.users):
                    # this author is already in this game, they don't need to be added
                    return
                if (
                    user.game
                    and user.game.id != game.id
                    and user.game.status != "started"
                ):
                    # this author is already another game, leave that one now
                    game_to_update = user.game
                    user.game_id = None
                    session.commit()
                    await self.try_to_update_game(game_to_update)
                user.game = game
            else:  # emoji == "🚫":
                if not any(user.xid == game_user.xid for game_user in game.users):
                    # this author is not in this game, so they can't be removed from it
                    return

                # update the game and remove the user from the game
                game.updated_at = now
                game.expires_at = expires_at
                user.game_id = None
                session.commit()

                # update the game message
                await safe_edit_message(message, embed=game.to_embed())
                return

            game.updated_at = now
            game.expires_at = expires_at
            session.commit()

            found_discord_users = []
            if len(game.users) == game.size:
                for game_user in game.users:
                    discord_user = await safe_fetch_user(self, game_user.xid)
                    if not discord_user:  # user has left the server since signing up
                        game_user.game_id = None
                    else:
                        found_discord_users.append(discord_user)

            if len(found_discord_users) == game.size:  # game is ready
                game.url = self.create_game() if game.system == "spelltable" else None
                game.status = "started"
                game.game_power = game.power
                session.commit()
                for discord_user in found_discord_users:
                    await discord_user.send(embed=game.to_embed(dm=True))
                await safe_edit_message(message, embed=game.to_embed())
                await safe_clear_reactions(message)
            else:
                session.commit()
                await safe_edit_message(message, embed=game.to_embed())

    async def on_message(self, message: discord.Message) -> None:
        """Behavior when the client gets a message from Discord."""
        try:
            author = cast(discord.User, message.author)

            # don't respond to any bots
            if author.bot:
                return

            private = str(message.channel.type) == "private"

            # only respond in text channels and to direct messages
            if not private and str(message.channel.type) != "text":
                return

            # only respond to command-like messages
            if not private:
                rows = self.data.conn.execute(
                    text("SELECT prefix FROM servers WHERE guild_xid = :g"),
                    g=message.channel.guild.id,
                )
                prefixes = [row.prefix for row in rows]
                prefix = prefixes[0] if prefixes else "!"
            else:
                prefix = "!"
            if not message.content.startswith(prefix):
                return

            is_admin = author.permissions_in(message.channel).administrator
            if not private and not is_admin:
                async with self.session() as session:
                    server = self.ensure_server_exists(session, message.channel.guild.id)
                    if not server.bot_allowed_in(message.channel.id):
                        return

            await self.process(message, prefix)
        except Exception as e:
            logging.exception("unhandled exception: %s", e)
            raise

    async def on_ready(self) -> None:
        """Behavior when the client has successfully connected to Discord."""
        logger.debug("logged in as %s", self.user)

    ##############################
    # Bot Command Functions
    ##############################

    # Any method of this class with a name that is decorated by @command is detected as a
    # bot command. These methods should have a signature like:
    #
    #     @command(allow_dm=True, admin_only=False, help_group="Hi")
    #     def command_name(self, session, prefix, params, message)
    #
    # - `allow_dm` indicates if the command is allowed to be used in direct messages.
    # - `admin_only` indicates if the command is available only to admins.
    # - `help_group` is the group name for this command in the usage help response.
    # - `session` is a database session, you must commit any changes you make.
    # - `prefix` is the command prefix, which is "!" by default.
    # - `params` are any space delimitered parameters also sent with the command.
    # - `message` is the discord.py message object that triggered the command.
    #
    # The docstring used for the command method will be automatically used as the help
    # message for the command. To document commands with parameters use a & to delimit
    # the help message from the parameter documentation. For example:
    #
    #     """This is the help message for your command. & <and> [these] [are] [params]"""
    #
    # Where [foo] indicates foo is optional and <bar> indicates bar is required.

    @command(allow_dm=True, help_group="Commands for Players")
    async def help(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Sends you this help message.
        """
        usage = ""
        command_methods = [getattr(self, command) for command in set(self.commands)]

        def method_sort_key(method):
            return method.help_group + method.__name__

        help_group: Optional[str] = None
        for method in sorted(command_methods, key=method_sort_key, reverse=True):
            if not help_group or method.help_group != help_group:
                help_group = method.help_group
                assert help_group
                usage += f"\n**### {help_group} ###**\n"

            doc = method.__doc__.split("&")
            cmd_params: List[str] = [param.strip() for param in doc[1:]]
            use, cmd_params_use = doc[0], ", ".join(cmd_params)
            use = inspect.cleandoc(use)

            transformed = ""
            for line in use.split("\n"):
                if line:
                    if line.startswith("*"):
                        transformed += f"\n{line}"
                    else:
                        transformed += f"{line} "
                else:
                    transformed += "\n\n"
            use = transformed
            use = use.replace("\n", "\n> ")
            use = re.sub(r"([^>])\s+$", r"\1", use, flags=re.M)

            title = f"{prefix}{method.__name__}"
            if cmd_params_use:
                title = f"{title} {cmd_params_use}"
            usage += f"\n`{title}`"
            usage += f"\n>  {use}"
            usage += "\n"
        usage += "---\n"
        usage += (
            "Please report any bugs and suggestions at"
            " <https://github.com/lexicalunit/spellbot/issues>!\n"
        )
        usage += "\n"
        usage += f"🔗 Add SpellBot to your Discord: <{INVITE_LINK}>\n"
        usage += "\n"
        usage += f"👍 Give SpellBot a vote on top.gg: <{VOTE_LINK}>\n"
        usage += "\n"
        usage += (
            "💜 You can help keep SpellBot running by supporting me on Ko-fi! "
            "<https://ko-fi.com/Y8Y51VTHZ>"
        )
        if str(message.channel.type) != "private":
            await safe_react_ok(message)
        for page in paginate(usage):
            await message.author.send(page)

    @command(allow_dm=True, help_group="Commands for Players")
    async def about(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Get information about SpellBot.
        """
        embed = discord.Embed(title="SpellBot")
        embed.set_thumbnail(url=THUMB_URL)
        version = f"[{__version__}](https://pypi.org/project/spellbot/{__version__}/)"
        embed.add_field(name="Version", value=version)
        author = "[@lexicalunit](https://github.com/lexicalunit)"
        embed.add_field(name="Author", value=author)
        embed.description = (
            "_The Discord bot for [SpellTable](https://www.spelltable.com/)._\n"
            "\n"
            f"Use the command `{prefix}help` for usage details. "
            "Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
            "\n"
            f"[🔗 Add SpellBot to your Discord!]({INVITE_LINK})\n"
            "\n"
            f"[👍 Give SpellBot a vote on top.gg!]({VOTE_LINK})\n"
            "\n"
            "💜 Help keep SpellBot running by "
            "[supporting me on Ko-fi!](https://ko-fi.com/Y8Y51VTHZ)"
        )
        embed.url = "http://spellbot.io/"
        embed.color = discord.Color(0x5A3EFD)
        await message.channel.send(embed=embed)
        await safe_react_ok(message)

    async def _validate_size(self, msg: discord.Message, size: Optional[int]) -> bool:
        if not size or not (1 < size < 5):
            user_xid = cast(discord.User, msg.author).id
            await msg.channel.send(s("game_size_bad", reply=f"<@{user_xid}>"))
            return False
        return True

    async def _validate_mentions_size(
        self, msg: discord.Message, mentions: List[Any], size: int
    ) -> bool:
        if len(mentions) + 1 >= size:
            user_xid = cast(discord.User, msg.author).id
            await msg.channel.send(s("lfg_too_many_mentions", reply=f"<@{user_xid}>"))
            return False
        return True

    async def _validate_tags_size(self, msg: discord.Message, tags: List[str]) -> bool:
        if len(tags) > 5:
            user_xid = cast(discord.User, msg.author).id
            await msg.channel.send(s("tags_too_many", reply=f"<@{user_xid}>"))
            return False
        return True

    async def _remove_user_from_game(self, session: Session, user: User):
        """If the user is currently in a game, take them out of it."""
        if user.waiting:
            game_to_update = user.game
            user.game_id = None
            session.commit()
            await self.try_to_update_game(game_to_update)

    async def _respond_found_game(
        self, msg: discord.Message, user: User, game: Game
    ) -> Optional[discord.Message]:
        # TODO: games will always have a message_xid even tho it's nullable in the db...
        assert game.message_xid
        post = await safe_fetch_message(msg.channel, game.message_xid, game.guild_xid)
        if not post:
            return None
        link = post_link(game.server.guild_xid, msg.channel.id, game.message_xid)
        resp = s("play_found", reply=f"<@{user.xid}>", link=link)
        await msg.channel.send(resp)
        return post

    async def _add_user_to_game(self, session: Session, user: User, game: Game) -> None:
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=game.server.expire)
        user.game = game
        user.game.expires_at = expires_at
        user.game.updated_at = now
        session.commit()

    async def _post_new_game(
        self, session: Session, msg: discord.Message, game: Game
    ) -> discord.Message:
        post = await msg.channel.send(embed=game.to_embed())
        game.message_xid = post.id
        session.commit()
        await post.add_reaction("✋")
        await post.add_reaction("🚫")
        return post

    async def _update_or_start_game(
        self, session: Session, game: Game, post: discord.Message
    ) -> None:
        if len(cast(List[User], game.users)) == game.size:  # game *might* be ready...
            found_discord_users = []
            for game_user in game.users:
                discord_user = await safe_fetch_user(self, game_user.xid)
                if not discord_user:  # user has left the server since signing up
                    await self._remove_user_from_game(session, game_user)
                else:
                    found_discord_users.append(discord_user)
            if len(found_discord_users) == game.size:  # game is *definitely* ready!
                game.url = self.create_game() if game.system == "spelltable" else None
                game.status = "started"
                game.game_power = game.power
                session.commit()
                for discord_user in found_discord_users:
                    await discord_user.send(embed=game.to_embed(dm=True))
                await safe_edit_message(post, embed=game.to_embed())
                await safe_clear_reactions(post)
                return
        else:  # game *definitely* isn't ready yet
            await safe_edit_message(post, embed=game.to_embed())

    async def _play_helper(
        self,
        session: Session,
        prefix: str,
        params: List[str],
        message: discord.Message,
        create_new_game: bool,
    ) -> None:
        server = self.ensure_server_exists(session, message.channel.guild.id)
        user = self.ensure_user_exists(session, message.author)
        mentions = message.mentions if message.channel.type != "private" else []

        opts = parse_opts(params)
        size: Optional[int] = opts["size"]
        tag_names: List[str] = opts["tags"]
        system: str = opts["system"]

        if not await self._validate_size(message, size):
            await safe_react_error(message)
            return
        assert size  # it's been validated, but pylance can't figure that out

        if not await self._validate_mentions_size(message, mentions, size):
            await safe_react_error(message)
            return
        mentioned_users: List[User] = [
            self.ensure_user_exists(session, mentioned) for mentioned in mentions
        ]

        if not await self._validate_tags_size(message, tag_names):
            await safe_react_error(message)
            return
        tags = Tag.create_many(session, tag_names)

        if mentioned_users:
            other = mentioned_users[0]
            for mentioned_user in mentioned_users:
                if not mentioned_user.waiting or mentioned_user.game != other.game:
                    await message.channel.send(
                        s("lfg_mentions_different_games", reply=f"<@{user.xid}>")
                    )
                    await safe_react_error(message)
                    return
            await self._remove_user_from_game(session, user)
            await self._add_user_to_game(session, user, other.game)
            game_post = await self._respond_found_game(message, user, other.game)
            if not game_post:
                game_post = await self._post_new_game(session, message, other.game)
            await self._update_or_start_game(session, other.game, game_post)
            await safe_react_ok(message)
            return

        new_game = False
        game = Game.find_existing(
            session=session,
            server=server,
            channel_xid=message.channel.id,
            size=size,
            seats=1,
            tags=tags,
            system=system,
            power=user.power,
        )

        if not game:
            if not create_new_game:
                await message.channel.send(s("game_not_found", reply=f"<@{user.xid}>"))
                await safe_react_error(message)
                return

            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=server.expire)
            new_game = True
            game = Game(
                created_at=now,
                updated_at=now,
                expires_at=expires_at,
                size=size,
                channel_xid=message.channel.id,
                system=system,
                tags=tags,
                server=server,
            )

        await self._remove_user_from_game(session, user)
        await self._add_user_to_game(session, user, game)

        post: Optional[discord.Message] = None
        if new_game:
            post = await self._post_new_game(session, message, game)
        else:
            post = await self._respond_found_game(message, user, game)
            if not post:  # the post must have been deleted
                post = await self._post_new_game(session, message, game)

        await self._update_or_start_game(session, game, post)
        await safe_react_ok(message)

    @command(allow_dm=False, help_group="Commands for Players")
    async def lfg(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Find or create a pending game for players to join.

        The default game size is 4 but you can change it by adding, for example, `size:2`
        to create a two player game.

        You can automatically join players already in a game by @ mentioning them in the
        command.

        Players will be able to enter or leave the game by reacting to the message that
        SpellBot sends with the ✋ and 🚫 emoji.

        Up to five tags can be given as well to help describe the game experience that you
        want. For example you might send `!lfg ~no-combo ~proxy` which will assign the
        tags `no-combo` and `proxy` to your game. People will be able to see what tags
        are set on your game when they are looking for games to join.
        & [size:N] [@player-1] [@player-2] ... [~tag-1] [~tag-2] ...
        """
        await self._play_helper(session, prefix, params, message, create_new_game=True)

    @command(allow_dm=False, help_group="Commands for Players")
    async def find(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Works exactly like `!lfg` except that it will NOT create a new game.
        """
        await self._play_helper(session, prefix, params, message, create_new_game=False)

    async def _verify_command_fest_report(
        self,
        session: Session,
        prefix: str,
        params: List[str],
        message: discord.Message,
        game: Game,
    ) -> bool:
        server = self.ensure_server_exists(session, message.channel.guild.id)
        mentioned_users = []
        for mentioned in message.mentions:
            mentioned_user = self.ensure_user_exists(session, mentioned)
            mentioned_users.append(mentioned_user)

        points = []
        for param in params[1:]:
            if param.isdigit():
                points.append(int(param))

        if len(mentioned_users) < 1:
            await message.channel.send(
                s(
                    "report_wrong",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    prefix=prefix,
                )
            )
            return False

        if len(mentioned_users) == len(points):
            for mentioned_user, pointage in zip(mentioned_users, points):
                user_points = (
                    session.query(UserPoints)
                    .filter_by(
                        user_xid=mentioned_user.xid,
                        guild_xid=server.guild_xid,
                        game_id=game.id,
                    )
                    .one_or_none()
                )
                if not user_points:
                    user_points = UserPoints(
                        user_xid=mentioned_user.xid,
                        guild_xid=server.guild_xid,
                        game_id=game.id,
                        points=pointage,
                    )
                    session.add(user_points)
                else:
                    user_points.points = pointage
            session.commit()
        else:
            await message.channel.send(
                s(
                    "report_wrong",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    prefix=prefix,
                )
            )
            return False

        return True

    @command(allow_dm=False, help_group="Commands for Players")
    async def report(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Report your results on a finished game.
        & <Game ID> ...
        """
        if len(params) < 2:
            await message.channel.send(
                s("report_no_params", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        req = params[0]
        report_str = " ".join(params[1:])

        if len(report_str) >= 255:
            await message.channel.send(
                s("report_too_long", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        game: Optional[Game] = None
        if req.lower().startswith("#sb") and req[3:].isdigit():
            game_id = int(req[3:])
            game = session.query(Game).filter(Game.id == game_id).one_or_none()
        elif req.lower().startswith("sb") and req[2:].isdigit():
            game_id = int(req[2:])
            game = session.query(Game).filter(Game.id == game_id).one_or_none()
        elif req.isdigit():
            game_id = int(req)
            game = session.query(Game).filter(Game.id == game_id).one_or_none()
        elif re.match(r"^[\w-]*$", req):  # perhaps it's a spellbot game id
            game = session.query(Game).filter(Game.url.ilike(f"%{req}")).one_or_none()

        if not game:
            await message.channel.send(
                s("report_no_game", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        if not game.status == "started":
            await message.channel.send(
                s(
                    "report_not_started",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        # TODO: This reporting logic is specific to CommandFest, it would be nice
        #       to refactor this to be more flexible after the event.
        verified = await self._verify_command_fest_report(
            session=session, prefix=prefix, params=params, message=message, game=game
        )
        if not verified:
            await safe_react_error(message)
            return

        report = Report(game_id=game.id, report=report_str)
        session.add(report)
        session.commit()
        await message.channel.send(
            s("report", reply=f"<@{cast(discord.User, message.author).id}>")
        )
        await safe_react_ok(message)

    @command(allow_dm=False, admin_only=False, help_group="Commands for Players")
    async def points(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Get your total points on this server.
        """
        user = self.ensure_user_exists(session, message.author)
        server = self.ensure_server_exists(session, message.channel.guild.id)
        points = user.points(server.guild_xid)

        await message.channel.send(
            s(
                "points",
                reply=f"<@{cast(discord.User, message.author).id}>",
                points=points,
            )
        )

        if is_admin(message.channel, message.author):
            team_points = Team.points(session, message.channel.guild.id)
            for team, team_points in team_points.items():
                await message.channel.send(
                    s(
                        "points_team",
                        reply=f"<@{cast(discord.User, message.author).id}>",
                        team=team,
                        points=team_points,
                    )
                )

        await safe_react_ok(message)

    @command(allow_dm=False, admin_only=True, help_group="Commands for Admins")
    async def event(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Create many games in batch from an attached CSV data file. _Requires the
        "SpellBot Admin" role._

        For example, if your event is for a Modern tournement you might attach a CSV file
        with a comment like `!event Player1Username Player2Username`. This would assume
        that the players' discord user names are found in the "Player1Username" and
        "Player2Username" CSV columns. The game size is deduced from the number of column
        names given, so we know the games created in this example are `size:2`.

        Games will not be created immediately. This is to allow you to verify things look
        ok. This command will also give you directions on how to actually start the games
        for this event as part of its reply.
        * Optional: Add a message to DM players with `msg:` followed by whatever.
        * Optional: Add up to five tags by using `~tag-name`.
        & <column 1> <column 2> ... [~tag-1 ~tag-2 ...] [msg: An optional message!]
        """
        if not message.attachments:
            await message.channel.send(
                s("event_no_data", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return
        if not params:
            await message.channel.send(
                s("event_no_params", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        opts = parse_opts(params)
        params, tag_names, opt_msg, system = (
            opts["params"],
            opts["tags"],
            opts["message"],
            opts["system"],
        )
        size = len(params)
        attachment = message.attachments[0]

        if len(tag_names) > 5:
            await message.channel.send(
                s("tags_too_many", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return
        if opt_msg and len(opt_msg) >= 255:
            await message.channel.send(
                s(
                    "game_message_too_long",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return
        if not (1 < size <= 4):
            await message.channel.send(
                s(
                    "event_bad_play_count",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return
        if not attachment.filename.lower().endswith(".csv"):
            await message.channel.send(
                s("event_not_csv", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        tags = Tag.create_many(session, tag_names)

        bdata = await message.attachments[0].read()
        sdata = bdata.decode("utf-8")

        server = self.ensure_server_exists(session, message.channel.guild.id)
        reader = csv.reader(StringIO(sdata))
        header = [column.lower().strip() for column in next(reader)]
        params = [param.lower().strip() for param in params]

        if any(param not in header for param in params):
            await message.channel.send(
                s("event_no_header", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        columns = [header.index(param) for param in params]

        event = Event()
        session.add(event)
        session.commit()

        players_in_this_event: Set[str] = set()
        warnings = set()

        members = message.channel.guild.members
        member_lookup = {member.name.lower().strip(): member for member in members}
        for i, row in enumerate(reader):
            csv_row_data = [row[column].strip() for column in columns]
            players_s = ", ".join([f'"{value}"' for value in csv_row_data])
            player_lnames = [
                re.sub("#.*$", "", value.lower()).lstrip("@") for value in csv_row_data
            ]

            if any(not lname for lname in player_lnames):
                warning = s("event_missing_player", row=i + 1, players=players_s)
                await message.channel.send(warning)
                continue

            player_discord_users: List[discord.User] = []
            for csv_data, lname in zip(csv_row_data, player_lnames):
                if lname in players_in_this_event:
                    await message.channel.send(
                        s(
                            "event_duplicate_user",
                            row=i + 1,
                            name=csv_data,
                            players=players_s,
                        )
                    )
                    await safe_react_error(message)
                    return
                player_discord_user = member_lookup.get(lname)
                if player_discord_user:
                    players_in_this_event.add(lname)
                    player_discord_users.append(player_discord_user)
                else:
                    warnings.add(
                        s(
                            "event_missing_user",
                            row=i + 1,
                            name=csv_data,
                            players=players_s,
                        )
                    )

            if len(player_discord_users) != size:
                continue

            player_users = [
                self.ensure_user_exists(session, player_discord_user)
                for player_discord_user in player_discord_users
            ]

            for player_discord_user, player_user in zip(
                player_discord_users, player_users
            ):
                if player_user.waiting:
                    game_to_update = player_user.game
                    player_user.game_id = None
                    await self.try_to_update_game(game_to_update)
                player_user.cached_name = player_discord_user.name
            session.commit()

            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=server.expire)
            game = Game(
                created_at=now,
                expires_at=expires_at,
                guild_xid=message.channel.guild.id,
                size=size,
                updated_at=now,
                status="ready",
                system=system,
                message=opt_msg,
                users=player_users,
                event=event,
                tags=tags,
            )
            session.add(game)
            session.commit()

        def by_row(s: str) -> int:
            m = re.match("^.*row ([0-9]+).*$", s)
            # TODO: Hopefully no one adds a strings.yaml warning
            #       that doesn't fit this exact format!
            assert m is not None
            return int(m[1])

        warnings_s = "\n".join(sorted(warnings, key=by_row))
        if warnings_s:
            for page in paginate(warnings_s):
                await message.channel.send(page)

        if not event.games:
            session.delete(event)
            await message.channel.send(
                s("event_empty", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        session.commit()
        count = len([game for game in event.games])
        await message.channel.send(
            s(
                "event_created",
                reply=f"<@{cast(discord.User, message.author).id}>",
                prefix=prefix,
                event_id=event.id,
                count=count,
            )
        )
        await safe_react_ok(message)

    @command(allow_dm=False, admin_only=True, help_group="Commands for Admins")
    async def begin(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Confirm creation of games for the given event id. _Requires the
        "SpellBot Admin" role._
        & <event id>
        """
        if not params:
            await message.channel.send(
                s("begin_no_params", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        event_id = to_int(params[0])
        if not event_id:
            await message.channel.send(
                s("begin_bad_event", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        event = session.query(Event).filter(Event.id == event_id).one_or_none()
        if not event:
            await message.channel.send(
                s("begin_bad_event", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        if event.started:
            await message.channel.send(
                s(
                    "begin_event_already_started",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        for game in event.games:
            # Can't rely on "<@{xid}>" working because the user could have logged out.
            sorted_names: List[str] = sorted([user.cached_name for user in game.users])
            players_str = ", ".join(sorted_names)

            found_discord_users = []
            for game_user in game.users:
                discord_user = await safe_fetch_user(self, game_user.xid)
                if not discord_user:  # game_user has left the server since event created
                    warning = s("begin_user_left", players=players_str)
                    await message.channel.send(warning)
                else:
                    found_discord_users.append(discord_user)
            if len(found_discord_users) != len(game.users):
                continue

            game.url = self.create_game() if game.system == "spelltable" else None
            game.status = "started"
            game.game_power = game.power
            response = game.to_embed(dm=True)
            session.commit()

            for discord_user in found_discord_users:
                await discord_user.send(embed=response)

            await message.channel.send(
                s(
                    "game_created",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    id=game.id,
                    url=game.url,
                    players=players_str,
                )
            )
            await safe_react_ok(message)

    @command(allow_dm=False, admin_only=True, help_group="Commands for Admins")
    async def game(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Create a game between mentioned users. _Requires the "SpellBot Admin" role._

        Allows event runners to spin up an ad-hoc game directly between mentioned players.
        * The user who issues this command is **NOT** added to the game themselves.
        * You must mention all of the players to be seated in the game.
        * Optional: Add a message by using `msg:` followed by the message content.
        * Optional: Add tags by using `~tag-name` for the tags you want.
        & @player1 @player2 ... [~tag-1 ~tag-2] [msg: Hello world!]
        """
        opts = parse_opts(params)
        size, tag_names, opt_msg, system = (
            opts["size"],
            opts["tags"],
            opts["message"],
            opts["system"],
        )
        mentions = message.mentions if message.channel.type != "private" else []

        if opt_msg and len(opt_msg) >= 255:
            await message.channel.send(
                s(
                    "game_message_too_long",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return
        if tag_names and len(tag_names) > 5:
            await message.channel.send(
                s("tags_too_many", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        if not size or not (1 < size <= 4):
            await message.channel.send(
                s("game_size_bad", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        if len(mentions) > size:
            await message.channel.send(
                s(
                    "game_too_many_mentions",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    size=size,
                )
            )
            await safe_react_error(message)
            return

        if len(mentions) < size:
            await message.channel.send(
                s(
                    "game_too_few_mentions",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    size=size,
                )
            )
            await safe_react_error(message)
            return

        mentioned_users = []
        for mentioned in mentions:
            mentioned_user = self.ensure_user_exists(session, mentioned)
            if mentioned_user.waiting:
                game_to_update = mentioned_user.game
                mentioned_user.game_id = None
                await self.try_to_update_game(game_to_update)
            mentioned_users.append(mentioned_user)
        session.commit()

        tags = Tag.create_many(session, tag_names)

        server = self.ensure_server_exists(session, message.channel.guild.id)

        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=server.expire)
        url = self.create_game() if system == "spelltable" else None
        game = Game(
            channel_xid=message.channel.id,
            created_at=now,
            expires_at=expires_at,
            guild_xid=server.guild_xid,
            size=size,
            updated_at=now,
            url=url,
            status="started",
            system=system,
            message=opt_msg,
            users=mentioned_users,
            tags=tags,
        )
        session.add(game)
        session.commit()

        player_response = game.to_embed(dm=True)
        for player in mentioned_users:
            discord_user = await safe_fetch_user(self, player.xid)
            # TODO: What happens if discord_user is None?
            if discord_user:
                await discord_user.send(embed=player_response)

        players_str = ", ".join(sorted([f"<@{user.xid}>" for user in mentioned_users]))
        await message.channel.send(
            s(
                "game_created",
                reply=f"<@{cast(discord.User, message.author).id}>",
                id=game.id,
                url=game.url,
                players=players_str,
            )
        )
        await safe_react_ok(message)

    @command(allow_dm=True, help_group="Commands for Players")
    async def leave(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Leave any pending games that you've signed up.
        """
        user = self.ensure_user_exists(session, message.author)
        if user.waiting:
            game = user.game
            user.game_id = None
            session.commit()
            await self.try_to_update_game(game)
        await safe_react_ok(message)

    @command(allow_dm=False, admin_only=True, help_group="Commands for Admins")
    async def export(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Exports historical game data to a CSV file. _Requires the "SpellBot Admin" role._
        """
        server = self.ensure_server_exists(session, message.channel.guild.id)
        export_file = TMP_DIR / f"{message.channel.guild.name}.csv"
        channel_name_cache = {}
        data = server.games_data()
        with open(export_file, "w") as f, redirect_stdout(f):
            print(  # noqa: T001
                "id,size,status,system,channel,url,event_id,created_at,tags,message"
            )
            for i in range(len(data["id"])):
                channel_xid = data["channel_xid"][i]
                if channel_xid and channel_xid not in channel_name_cache:
                    channel = await safe_fetch_channel(
                        self, int(channel_xid), message.channel.guild.id
                    )
                    if channel:
                        name = cast(TextChannel, channel).name
                        channel_name_cache[channel_xid] = f"#{name}"
                    else:
                        channel_name_cache[channel_xid] = f"<#{channel_xid}>"
                print(  # noqa: T001
                    ",".join(
                        [
                            data["id"][i],
                            data["size"][i],
                            data["status"][i],
                            data["system"][i],
                            channel_name_cache[channel_xid] if channel_xid else "",
                            data["url"][i],
                            data["event_id"][i],
                            data["created_at"][i],
                            data["tags"][i],
                            data["message"][i],
                        ]
                    )
                )
        await message.channel.send("", file=discord.File(export_file))
        await safe_react_ok(message)

    @command(allow_dm=True, help_group="Commands for Players")
    async def power(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Set or unset the power level of the deck you are going to play.
        **You DO NOT NEED to have a power level set to use SpellBot.**

        When you have set a power level, the !lfg and !find commands will try to put
        you in games with other players of similar power levels.
        & <none | 1..10>
        """

        async def send_invalid(prepend) -> None:
            await message.channel.send(
                s(
                    "power_invalid",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    prepend=prepend,
                )
            )
            await safe_react_error(message)

        if not params:
            return await send_invalid("")

        user = self.ensure_user_exists(session, message.author)

        power = params[0].lower()
        if power in ["none", "off", "unset", "no", "0"]:
            user.power = None
            session.commit()
            await safe_react_ok(message)
            if user.waiting:
                await self.try_to_update_game(user.game)
            await safe_react_ok(message)
            return

        if power == "unlimited":
            return await send_invalid("⚡ ")

        if not power.isdigit():
            return await send_invalid("")

        power_i = int(power)
        if not (1 <= power_i <= 10):
            prepend = ""
            if power_i == 11:
                prepend = "🤘 "
            elif power_i == 9000:
                prepend = "💥 "
            elif power_i == 42:
                prepend = "🤖 "
            return await send_invalid(prepend)

        user.power = power_i
        session.commit()
        await safe_react_ok(message)
        if user.waiting:
            await self.try_to_update_game(user.game)
        await safe_react_ok(message)

    @command(allow_dm=False, help_group="Commands for Players")
    async def team(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Set or get your team on this server. To get your team name, run this command with
        no parameters.
        & [team-name]
        """
        server = self.ensure_server_exists(session, message.channel.guild.id)
        if not server.teams:
            await message.channel.send(
                s("team_none", reply=f"<@{cast(discord.User, message.author).id}>")
            )
            await safe_react_error(message)
            return

        user = self.ensure_user_exists(session, message.author)
        if not params:
            user_team = (
                session.query(UserTeam)
                .filter_by(user_xid=user.xid, guild_xid=server.guild_xid)
                .one_or_none()
            )

            if not user_team:
                await message.channel.send(
                    s("team_not_set", reply=f"<@{cast(discord.User, message.author).id}>")
                )
                await safe_react_error(message)
                return

            team = session.query(Team).filter_by(id=user_team.team_id).one_or_none()
            if not team:
                session.delete(user_team)
                await message.channel.send(
                    s("team_gone", reply=f"<@{cast(discord.User, message.author).id}>")
                )
                await safe_react_error(message)
                return

            await message.channel.send(
                s(
                    "team_yours",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    team=team.name,
                )
            )
            await safe_react_ok(message)
            return

        team_request = params[0]
        team_found: Optional[Team] = None
        for team in server.teams:
            if team_request.lower() != team.name.lower():
                continue
            team_found = team
            break

        if not team_found:
            teams = ", ".join(sorted(team.name for team in server.teams))
            await message.channel.send(
                s(
                    "team_not_found",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    teams=teams,
                ),
            )
            await safe_react_error(message)
            return

        user_team = (
            session.query(UserTeam)
            .filter_by(user_xid=user.xid, guild_xid=server.guild_xid)
            .one_or_none()
        )
        if user_team:
            user_team.team_id = team_found.id
        else:
            user_team = UserTeam(
                user_xid=user.xid, guild_xid=server.guild_xid, team_id=team_found.id
            )
            session.add(user_team)
        session.commit()
        await safe_react_ok(message)

    @command(allow_dm=False, help_group="Commands for Admins")
    async def spellbot(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Configure SpellBot for your server. _Requires the "SpellBot Admin" role._

        The following subcommands are supported:
        * `config`: Just show the current configuration for this server.
        * `channel <list>`: Set SpellBot to only respond in the given list of channels.
        * `prefix <string>`: Set SpellBot's command prefix for text channels.
        * `links <string>`: Set the privacy level for generated SpellTable links.
        * `expire <number>`: Set the number of minutes before pending games expire.
        * `teams <list>`: Sets the teams available on this server.
        * `help`: Get detailed usage help for SpellBot.
        & <subcommand> [subcommand parameters]
        """
        if not params:
            await message.channel.send(
                s(
                    "spellbot_missing_subcommand",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        command = params[0]
        if command == "help":
            await self.spellbot_help(session, prefix, params[1:], message)
            return

        if not await check_is_admin(message):
            await safe_react_error(message)
            return

        server = self.ensure_server_exists(session, message.channel.guild.id)
        if command == "channels":
            await self.spellbot_channels(session, server, params[1:], message)
        elif command == "prefix":
            await self.spellbot_prefix(session, server, params[1:], message)
        elif command == "expire":
            await self.spellbot_expire(session, server, params[1:], message)
        elif command == "config":
            await self.spellbot_config(session, server, params[1:], message)
        elif command == "links":
            await self.spellbot_links(session, server, params[1:], message)
        elif command == "teams":
            await self.spellbot_teams(session, server, params[1:], message)
        else:
            await message.channel.send(
                s(
                    "spellbot_unknown_subcommand",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    command=command,
                )
            )
            await safe_react_error(message)

    async def spellbot_channels(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await message.channel.send(
                s(
                    "spellbot_channels_none",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        # Blow away the current associations first, otherwise SQLAlchemy will explode.
        session.query(Channel).filter_by(guild_xid=server.guild_xid).delete()

        all_channels = False
        channels = []
        for param in params:
            if param.lower() == "all":
                all_channels = True
                break

            m = re.match("<#([0-9]+)>", param)
            if not m:
                await message.channel.send(
                    s(
                        "spellbot_channels_warn",
                        reply=f"<@{cast(discord.User, message.author).id}>",
                        param=param,
                    )
                )
                continue

            discord_channel = await safe_fetch_channel(self, int(m[1]), server.guild_xid)
            if not discord_channel:
                await message.channel.send(
                    s(
                        "spellbot_channels_warn",
                        reply=f"<@{cast(discord.User, message.author).id}>",
                        param=param,
                    )
                )
                continue

            channel = Channel(channel_xid=discord_channel.id, guild_xid=server.guild_xid)
            session.add(channel)
            channels.append(channel)
            session.commit()

        if all_channels:
            server.channels = []
            session.commit()
            await message.channel.send(
                s(
                    "spellbot_channels",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    channels="all channels",
                )
            )
        elif channels:
            server.channels = channels
            session.commit()
            channels_str = ", ".join([f"<#{c.channel_xid}>" for c in channels])
            await message.channel.send(
                s(
                    "spellbot_channels",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    channels=channels_str,
                )
            )
        await safe_react_ok(message)

    async def spellbot_prefix(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await message.channel.send(
                s(
                    "spellbot_prefix_none",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        prefix_str = params[0][0:10]
        server.prefix = prefix_str
        session.commit()
        await message.channel.send(
            s(
                "spellbot_prefix",
                reply=f"<@{cast(discord.User, message.author).id}>",
                prefix=prefix_str,
            )
        )
        await safe_react_ok(message)

    async def spellbot_links(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await message.channel.send(
                s(
                    "spellbot_links_none",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        links_str = params[0].lower()
        if links_str not in ["private", "public"]:
            await message.channel.send(
                s(
                    "spellbot_links_bad",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                    input=params[0],
                )
            )
            await safe_react_error(message)
            return

        server.links = links_str
        session.commit()
        await message.channel.send(
            s(
                "spellbot_links",
                reply=f"<@{cast(discord.User, message.author).id}>",
                setting=links_str,
            )
        )
        await safe_react_ok(message)

    async def spellbot_expire(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await message.channel.send(
                s(
                    "spellbot_expire_none",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        expire = to_int(params[0])
        if not expire or not (0 < expire <= 60):
            await message.channel.send(
                s(
                    "spellbot_expire_bad",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        server = (
            session.query(Server)
            .filter(Server.guild_xid == message.channel.guild.id)
            .one_or_none()
        )
        server.expire = expire
        session.commit()
        await message.channel.send(
            s(
                "spellbot_expire",
                reply=f"<@{cast(discord.User, message.author).id}>",
                expire=expire,
            )
        )
        await safe_react_ok(message)

    async def spellbot_teams(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await message.channel.send(
                s(
                    "spellbot_teams_none",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        erase_all_teams = params[0].lower() == "none"

        if len(params) < 2 and not erase_all_teams:
            await message.channel.send(
                s(
                    "spellbot_teams_too_few",
                    reply=f"<@{cast(discord.User, message.author).id}>",
                )
            )
            await safe_react_error(message)
            return

        # blow away any existing old teams
        for team in server.teams:
            session.delete(team)
        session.commit()

        if not erase_all_teams:
            # then create new ones
            server.teams = [Team(name=name) for name in set(params)]
            session.commit()

        await safe_react_ok(message)

    async def spellbot_config(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        embed = discord.Embed(title="SpellBot Server Config")
        embed.set_thumbnail(url=THUMB_URL)
        embed.add_field(name="Command prefix", value=server.prefix)
        expires_str = f"{server.expire} minutes"
        embed.add_field(name="Inactivity expiration time", value=expires_str)
        channels = sorted(server.channels, key=lambda channel: channel.channel_xid)
        if channels:
            channels_str = ", ".join(f"<#{channel.channel_xid}>" for channel in channels)
        else:
            channels_str = "all"
        embed.add_field(name="Active channels", value=channels_str)
        embed.add_field(name="Links", value=server.links.title())
        if server.teams:
            teams_str = ", ".join(sorted(team.name for team in server.teams))
            embed.add_field(name="Teams", value=teams_str)
        embed.color = discord.Color(0x5A3EFD)
        embed.set_footer(text=f"Config for Guild ID: {server.guild_xid}")
        await message.channel.send(embed=embed)
        await safe_react_ok(message)

    async def spellbot_help(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        await self.help(session, prefix, params, message)


def get_db_env(fallback: str) -> str:  # pragma: no cover
    """Returns the database env var from the environment or else the given fallback."""
    value = getenv("SPELLBOT_DB_ENV", fallback)
    return value or fallback


def get_db_url(database_env: str, fallback: str) -> str:  # pragma: no cover
    """Returns the database url from the environment or else the given fallback."""
    value = getenv(database_env, fallback)
    return value or fallback


def get_port_env(fallback: str) -> str:  # pragma: no cover
    """Returns the port env var from the environment or else the given fallback."""
    value = getenv("SPELLBOT_PORT_ENV", fallback)
    return value or fallback


def get_port(port_env: str, fallback: int) -> int:  # pragma: no cover
    """Returns the port from the environment or else the given fallback."""
    value = getenv(port_env, fallback)
    return int(value) or fallback


def get_host(fallback: str) -> str:  # pragma: no cover
    """Returns the hostname from the environment or else the given fallback."""
    value = getenv("SPELLBOT_HOST", fallback)
    return value or fallback


def get_log_level(fallback: str) -> str:  # pragma: no cover
    """Returns the log level from the environment or else the given gallback."""
    value = getenv("SPELLBOT_LOG_LEVEL", fallback)
    return value or fallback


async def ping(request):  # pragma: no cover
    return web.Response(text="ok")


@click.command()
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]),
    default="ERROR",
    help="Can also be set by the environment variable SPELLBOT_LOG_LEVEL.",
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
        "By default SpellBot looks in the environment variable SPELLBOT_DB_URL for the "
        "database connection string. If you need it to look in a different variable "
        "you can set it with this option. For example Heroku uses DATABASE_URL."
        "Can also be set by the environment variable SPELLBOT_DB_ENV."
    ),
)
@click.option(
    "-p",
    "--port",
    default=DEFAULT_PORT,
    help=(
        "HTTP server port to use; "
        "you can also set this via the SPELLBOT_PORT environment variable."
    ),
)
@click.option(
    "--port-env",
    default="SPELLBOT_PORT",
    help=(
        "By default SpellBot looks in the environment variable SPELLBOT_PORT for the "
        "HTTP port to use. If you need it to look in a different variable "
        "you can set it with this option. For example Heroku uses PORT."
        "Can also be set by the environment variable SPELLBOT_PORT_ENV."
    ),
)
@click.option(
    "--host",
    default=DEFAULT_HOST,
    help=(
        "HTTP server hostname to use; "
        "you can also set this via the SPELLBOT_HOST environment variable."
    ),
)
@click.version_option(version=__version__)
@click.option(
    "--dev",
    default=False,
    is_flag=True,
    help="Development mode, automatically reload bot when source changes",
)
@click.option(
    "--mock-games",
    default=False,
    is_flag=True,
    help="Produce mock game urls instead of real ones",
)
def main(
    log_level: str,
    verbose: int,
    database_url: str,
    database_env: str,
    port: int,
    port_env: str,
    host: str,
    dev: bool,
    mock_games: bool,
) -> None:  # pragma: no cover
    if dev:
        reloader = hupper.start_reloader("spellbot.main")
        reloader.watch_files(ASSET_FILES)

    database_env = get_db_env(database_env)
    database_url = get_db_url(database_env, database_url)
    port_env = get_port_env(port_env)
    port = get_port(port_env, port)
    host = get_host(host)
    log_level = get_log_level(log_level)

    # We have to make sure that application directories exist
    # before we try to create we can run any of the migrations.
    ensure_application_directories_exist()

    token = getenv("SPELLBOT_TOKEN", None)
    if not token:
        print(  # noqa: T001
            "error: SPELLBOT_TOKEN environment variable not set", file=sys.stderr
        )
        sys.exit(1)

    auth = getenv("SPELLTABLE_AUTH", None)
    if not auth and not mock_games:
        print(  # noqa: T001
            "error: SPELLTABLE_AUTH environment variable not set", file=sys.stderr
        )
        sys.exit(1)

    # simple http server to check for uptime
    loop = asyncio.get_event_loop()
    app = web.Application()
    app.router.add_get("/", ping)
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, host, port)
    loop.run_until_complete(site.start())

    client = SpellBot(
        token=token,
        auth=auth,
        db_url=database_url,
        log_level="DEBUG" if verbose else log_level,
        mock_games=mock_games,
        loop=loop,
    )
    logger.info(f"server running: http://{host}:{port}")
    client.run()


if __name__ == "__main__":
    main()
