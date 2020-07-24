import asyncio
import csv
import inspect
import logging
import re
import sys
from contextlib import asynccontextmanager, redirect_stdout
from datetime import datetime, timedelta
from functools import wraps
from io import StringIO
from os import getenv
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Iterator, List, Optional, Union, cast
from uuid import uuid4

import click
import discord
import discord.errors
import hupper  # type: ignore
import requests
from discord.channel import TextChannel
from sqlalchemy import exc
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import text

from spellbot._version import __version__
from spellbot.assets import ASSET_FILES, s
from spellbot.constants import ADMIN_ROLE, CREATE_ENDPOINT, DEFAULT_GAME_SIZE, THUMB_URL
from spellbot.data import Channel, Data, Event, Game, Server, Tag, User

# Application Paths
RUNTIME_ROOT = Path(".")
SCRIPTS_DIR = RUNTIME_ROOT / "scripts"
DB_DIR = RUNTIME_ROOT / "db"
DEFAULT_DB_URL = f"sqlite:///{DB_DIR}/spellbot.db"
TMP_DIR = RUNTIME_ROOT / "tmp"
MIGRATIONS_DIR = SCRIPTS_DIR / "migrations"


ChannelType = Union[
    discord.TextChannel,
    discord.VoiceChannel,
    discord.DMChannel,
    discord.CategoryChannel,
    discord.GroupChannel,
    discord.StoreChannel,
]


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

    for i, param in enumerate(params):
        if skip_next:
            skip_next = False
            continue

        if param.lower() in ["~mtgo", "~modo"]:
            system = "mtgo"
        elif param.lower() in ["~arena", "~mtga"]:
            system = "arena"
        elif param.startswith("~"):
            tags.append(param[1:].lower())
        elif param.lower().startswith("size:"):
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


def ensure_application_directories_exist() -> None:
    """Idempotent function to make sure needed application directories are there."""
    TMP_DIR.mkdir(exist_ok=True)
    DB_DIR.mkdir(exist_ok=True)


def paginate(text: str) -> Iterator[str]:
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
        yield message.rstrip(" >\n")
        remaining = remaining[breakpoint + 1 :]
        last_line_end = message.rfind("\n")
        if last_line_end != -1 and len(message) > last_line_end + 1:
            last_line_start = last_line_end + 1
        else:
            last_line_start = 0
        if message[last_line_start] == ">":
            remaining = f"> {remaining}"

    yield remaining


def command(allow_dm: bool = True) -> Callable:
    """Decorator for bot command methods."""

    def callable(func: Callable):
        @wraps(func)
        async def wrapped(*args, **kwargs) -> Any:
            return await func(*args, **kwargs)

        cast(Any, wrapped).is_command = True
        cast(Any, wrapped).allow_dm = allow_dm
        return wrapped

    return callable


class SpellBot(discord.Client):
    """Discord SpellTable Bot"""

    def __init__(
        self,
        token: str = "",
        auth: Optional[str] = "",
        db_url: str = DEFAULT_DB_URL,
        log_level: Union[int, str] = logging.ERROR,
        mock_games: bool = False,
    ):
        logging.basicConfig(level=log_level)
        loop = asyncio.get_event_loop()
        super().__init__(loop=loop)
        self.token = token
        self.auth = auth
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
    async def session(self) -> AsyncGenerator[Session, None]:  # pragma: no cover
        session = self.data.Session()
        try:
            yield session
        except exc.SQLAlchemyError as e:
            logging.exception("database error:", e)
            session.rollback()
            raise
        finally:
            session.close()

    async def safe_fetch_message(
        self, channel: ChannelType, message_xid: int
    ) -> Optional[discord.Message]:  # pragma: no cover
        if isinstance(
            channel, (discord.VoiceChannel, discord.CategoryChannel, discord.StoreChannel)
        ):
            return None
        try:
            return await channel.fetch_message(message_xid)
        except (
            discord.errors.HTTPException,
            discord.errors.NotFound,
            discord.errors.Forbidden,
        ) as e:
            logging.exception("warning: discord: could not fetch message", e)
            return None

    async def safe_fetch_channel(
        self, channel_xid: int
    ) -> Optional[ChannelType]:  # pragma: no cover
        channel = self.get_channel(channel_xid)
        if channel:
            return channel
        try:
            return await self.fetch_channel(channel_xid)
        except (
            discord.errors.InvalidData,
            discord.errors.HTTPException,
            discord.errors.NotFound,
            discord.errors.Forbidden,
        ) as e:
            logging.exception("warning: discord: could not fetch channel", e)
            return None

    async def safe_fetch_user(
        self, user_xid: int
    ) -> Optional[discord.User]:  # pragma: no cover
        user = self.get_user(user_xid)
        if user:
            return user
        try:
            return await self.fetch_user(user_xid)
        except (discord.errors.NotFound, discord.errors.HTTPException) as e:
            logging.exception("warning: discord: could fetch user", e)
            return None

    async def safe_remove_reaction(
        self, message: discord.Message, emoji: str, user: discord.User
    ) -> None:  # pragma: no cover
        try:
            await message.remove_reaction(emoji, user)
        except (
            discord.errors.HTTPException,
            discord.errors.Forbidden,
            discord.errors.NotFound,
            discord.errors.InvalidArgument,
        ) as e:
            logging.exception("warning: discord: could not remove reaction", e)

    async def safe_clear_reactions(
        self, message: discord.Message
    ) -> None:  # pragma: no cover
        try:
            await message.clear_reactions()
        except (discord.errors.HTTPException, discord.errors.Forbidden) as e:
            logging.exception("warning: discord: could not clear reactions", e)

    async def safe_edit_message(
        self, message: discord.Message, *, reason: str = None, **options
    ) -> None:  # pragma: no cover
        try:
            await message.edit(reason=reason, **options)
        except (
            discord.errors.InvalidArgument,
            discord.errors.Forbidden,
            discord.errors.HTTPException,
        ) as e:
            logging.exception("warning: discord: could not edit message", e)

    async def safe_delete_message(
        self, message: discord.Message
    ) -> None:  # pragma: no cover
        try:
            await message.delete()
        except (
            discord.errors.Forbidden,
            discord.errors.NotFound,
            discord.errors.HTTPException,
        ) as e:
            logging.exception("warning: discord: could not delete message", e)

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
                    discord_user = await self.safe_fetch_user(user.xid)
                    if discord_user:
                        await discord_user.send(s("expired", window=game.server.expire))
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

    def run(self) -> None:  # pragma: no cover
        super().run(self.token)

    def create_game(self) -> str:  # pragma: no cover
        if self.mock_games:
            return f"http://exmaple.com/game/{uuid4()}"
        else:
            headers = {"user-agent": f"spellbot/{__version__}", "key": self.auth}
            r = requests.post(CREATE_ENDPOINT, headers=headers)
            return cast(str, r.json()["gameUrl"])

    def ensure_user_exists(
        self, session: Session, user: Union[discord.User, discord.Member],
    ) -> User:
        """Ensures that the user row exists for the given discord user."""
        user_xid = cast(Any, user).id  # typing doesn't recognize that id exists
        db_user = session.query(User).filter(User.xid == user_xid).one_or_none()
        if not db_user:
            db_user = User(
                xid=user_xid,
                game_id=None,
                cached_name=cast(Any, user).name,
                invited=False,
                invite_confirmed=False,
            )
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
        """Attempts to remove a ➕ from the given game message for the given user."""
        if not game.channel_xid:
            return

        chan = await self.safe_fetch_channel(game.channel_xid)
        if not chan:
            return

        if not game.message_xid:
            return

        post = await self.safe_fetch_message(chan, game.message_xid)
        if not post:
            return

        await self.safe_delete_message(post)

    async def try_to_remove_plus(self, game, discord_user: discord.User) -> None:
        """Attempts to remove a ➕ from the given game message for the given user."""
        if not game.channel_xid:
            return

        chan = await self.safe_fetch_channel(game.channel_xid)
        if not chan:
            return

        post = await self.safe_fetch_message(chan, game.message_xid)
        if not post:
            return

        await self.safe_remove_reaction(post, "➕", discord_user)

    @property
    def commands(self) -> List[str]:
        """Returns a list of commands supported by this bot."""
        return self._commands

    async def process(self, message: discord.Message, prefix: str) -> None:
        """Process a command message."""
        tokens = message.content.split(" ")
        request, params = tokens[0].lstrip(prefix).lower(), tokens[1:]
        params = list(filter(None, params))  # ignore any empty string parameters
        if not request:
            return
        matching = [command for command in self.commands if command.startswith(request)]
        if not matching:
            await message.channel.send(s("not_a_command", request=request))
            return
        if len(matching) > 1 and request not in matching:
            possible = ", ".join(f"{prefix}{m}" for m in matching)
            await message.channel.send(s("did_you_mean", possible=possible))
            return
        else:
            command = request if request in matching else matching[0]
            method = getattr(self, command)
            if not method.allow_dm and str(message.channel.type) == "private":
                await message.author.send(s("no_dm"))
                return
            logging.debug(
                "%s%s (params=%s, message=%s)", prefix, command, params, message
            )
            async with self.session() as session:
                await method(session, prefix, params, message)
                return

    async def process_invite_response(
        self, message: discord.Message, choice: str
    ) -> None:
        async with self.session() as session:
            user = self.ensure_user_exists(session, message.author)

            if not user.invited:
                await message.author.send(s("invite_not_invited"))
                return

            if user.invite_confirmed:
                await message.author.send(s("invite_already_confirmed"))
                return

            game = user.game

            # TODO: currently the codebase should always assign a channel_xid to games,
            # can we update the models to have this column as non-nullable?
            assert game.channel_xid is not None

            if choice == "yes":
                user.invite_confirmed = True
                await message.author.send(s("invite_confirmed"))
            else:  # choice == "no":
                user.invited = False
                user.game_id = None
                await message.author.send(s("invite_denied"))
            session.commit()

            if all(
                not user.invited or (user.invited and user.invite_confirmed)
                for user in game.users
            ):
                channel = await self.safe_fetch_channel(game.channel_xid)
                if not channel or not hasattr(channel, "send"):
                    # This shouldn't be possible, if it happens just delete the game.
                    # TODO: Inform players that their game is being deleted.
                    err = f"process_invite_response: fetch channel {game.channel_xid}"
                    logging.error(err)
                    game.tags = []  # cascade delete tag associations
                    session.delete(game)
                    session.commit()
                    return

                post = await cast(TextChannel, channel).send(embed=game.to_embed())
                game.message_xid = post.id
                session.commit()
                await post.add_reaction("➕")
                await post.add_reaction("➖")

    ##############################
    # Discord Client Behavior
    ##############################

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Behavior when the client gets a new reaction on a Discord message."""
        emoji = str(payload.emoji)
        if emoji not in ["➕", "➖"]:
            return

        channel = await self.safe_fetch_channel(payload.channel_id)
        if not channel or str(channel.type) != "text":
            return

        # From the docs: payload.member is available if `event_type` is `REACTION_ADD`.
        author = cast(discord.User, payload.member)
        if author.bot:
            return

        message = await self.safe_fetch_message(channel, payload.message_id)
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
                return  # this isn't a post relating to a game, just ignore it

            user = self.ensure_user_exists(session, author)

            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=server.expire)

            await self.safe_remove_reaction(message, emoji, author)

            if emoji == "➕":
                if any(user.xid == game_user.xid for game_user in game.users):
                    # this author is already in this game, they don't need to be added
                    return
                if user.game and user.game.id != game.id:
                    # this author is already another game, they can't be added
                    await author.send(s("react_already_in", prefix=server.prefix))
                    return
                user.game = game
            else:  # emoji == "➖":
                if not any(user.xid == game_user.xid for game_user in game.users):
                    # this author is not in this game, so they can't be removed from it
                    return

                # update the game and remove the user from the game
                game.updated_at = now
                game.expires_at = expires_at
                user.game_id = None
                session.commit()

                # update the game message
                await self.safe_edit_message(message, embed=game.to_embed())
                return

            game.updated_at = now
            game.expires_at = expires_at
            session.commit()

            found_discord_users = []
            if len(game.users) == game.size:
                for game_user in game.users:
                    discord_user = await self.safe_fetch_user(game_user.xid)
                    if not discord_user:  # user has left the server since signing up
                        game_user.game_id = None
                    else:
                        found_discord_users.append(discord_user)

            if len(found_discord_users) == game.size:  # game is ready
                game.url = self.create_game() if game.system == "spelltable" else None
                game.status = "started"
                session.commit()
                for discord_user in found_discord_users:
                    await discord_user.send(embed=game.to_embed())
                await self.safe_edit_message(message, embed=game.to_embed())
                await self.safe_clear_reactions(message)
            else:
                session.commit()
                await self.safe_edit_message(message, embed=game.to_embed())

    async def on_message(self, message: discord.Message) -> None:
        """Behavior when the client gets a message from Discord."""
        # don't respond to any bots
        if cast(discord.User, message.author).bot:
            return

        private = str(message.channel.type) == "private"

        # only respond in text channels and to direct messages
        if not private and str(message.channel.type) != "text":
            return

        # handle confirm/deny invitations over direct message
        if private:
            choice = message.content.lstrip()[0:3].rstrip().lower()
            if choice in ["yes", "no"]:
                return await self.process_invite_response(message, choice)

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

        if not private:
            async with self.session() as session:
                server = self.ensure_server_exists(session, message.channel.guild.id)
                if not server.bot_allowed_in(message.channel.id):
                    return

        await self.process(message, prefix)

    async def on_ready(self) -> None:
        """Behavior when the client has successfully connected to Discord."""
        logging.debug("logged in as %s", self.user)

    ##############################
    # Bot Command Functions
    ##############################

    # Any method of this class with a name that is decorated by @command is detected as a
    # bot command. These methods should have a signature like:
    #
    #     @command(allow_dm=True)
    #     def command_name(self, prefix, params, message)
    #
    # - `allow_dm` indicates if the command is allowed to be used in direct messages.
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

    @command(allow_dm=True)
    async def help(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Sends you this help message.
        """
        usage = ""
        for command in self.commands:
            method = getattr(self, command)
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

            title = f"{prefix}{command}"
            if cmd_params_use:
                title = f"{title} {cmd_params_use}"
            usage += f"\n`{title}`"
            usage += f"\n>  {use}"
            usage += "\n"
        usage += "---"
        usage += (
            " \nPlease report any bugs and suggestions at"
            " <https://github.com/lexicalunit/spellbot/issues>!"
        )
        usage += "\n"
        usage += (
            "\n💜 You can help keep SpellBot running by supporting me on Ko-fi! "
            "<https://ko-fi.com/Y8Y51VTHZ>"
        )
        await message.channel.send(s("dm_sent"))
        for page in paginate(usage):
            await message.author.send(page)

    @command(allow_dm=True)
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
        embed.add_field(
            name="Package", value="[PyPI](https://pypi.org/project/spellbot/)"
        )
        author = "[@lexicalunit](https://github.com/lexicalunit)"
        embed.add_field(name="Author", value=author)
        embed.description = (
            "_A Discord bot for [SpellTable](https://www.spelltable.com/)._\n"
            "\n"
            f"Use the command `{prefix}help` for usage details. "
            "Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
            "\n"
            "💜 Help keep SpellBot running by "
            "[supporting me on Ko-fi!](https://ko-fi.com/Y8Y51VTHZ)"
        )
        embed.url = "https://github.com/lexicalunit/spellbot"
        embed.set_footer(text="MIT © amy@lexicalunit et al")
        embed.color = discord.Color(0x5A3EFD)
        await message.channel.send(embed=embed)

    @command(allow_dm=False)
    async def lfg(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Create a pending game for players to join.

        The default game size is 4 but you can change it by adding, for example, `size:2`
        to create a two player game.

        You can automatically invite players to the game by @ mentioning them in the
        command. They will be sent invite confirmations and the game won't be posted to
        the channel until they've responded.

        Players will be able to join or leave the game by reacting to the message that
        SpellBot sends with the ➕ and ➖ emoji.

        Up to five tags can be given as well to help describe the game expereince that you
        want. For example you might send `!lfg ~no-combo ~proxy` which will assign the
        tags: `no-combo` and `proxy` to your game. People will be able to see what tags
        are set on your game when they are looking for games to join.
        & [size:N] [~tag-1] [~tag-2] [...] [~tag-N]
        """
        server = self.ensure_server_exists(session, message.channel.guild.id)

        user = self.ensure_user_exists(session, message.author)
        if user.waiting:
            await message.channel.send(s("lfg_already", prefix=server.prefix))
            return

        mentions = message.mentions if message.channel.type != "private" else []

        opts = parse_opts(params)
        size, tag_names, system = opts["size"], opts["tags"], opts["system"]

        if not size or not (1 < size < 5):
            await message.channel.send(s("lfg_size_bad"))
            return

        if len(mentions) + 1 >= size:
            await message.channel.send(s("lfg_too_many_mentions"))
            return

        mentioned_users = []
        for mentioned in mentions:
            mentioned_user = self.ensure_user_exists(session, mentioned)
            if mentioned_user.waiting:
                await message.channel.send(
                    s("lfg_mention_already", mention=f"<@{mentioned.id}>")
                )
                return
            mentioned_users.append(mentioned_user)

        if len(tag_names) > 5:
            await message.channel.send(s("tags_too_many"))
            return
        tags = Tag.create_many(session, tag_names)

        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=server.expire)
        user.invited = False
        user.game = Game(
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            size=size,
            channel_xid=message.channel.id,
            system=system,
            tags=tags,
            server=server,
        )
        for mentioned_user in mentioned_users:
            mentioned_user.game = user.game
            mentioned_user.invited = True
            mentioned_user.invite_confirmed = False
        session.commit()

        mentionor = message.author
        mentionor_xid = cast(Any, mentionor).id  # typing doesn't recognize author.id

        if mentioned_users:
            for mentioned in mentions:
                await mentioned.send(s("lfg_invited", mention=f"<@{mentionor_xid}>"))
        else:
            post = await message.channel.send(embed=user.game.to_embed())
            user.game.message_xid = post.id
            session.commit()
            await post.add_reaction("➕")
            await post.add_reaction("➖")

    @command(allow_dm=False)
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
        * Optional: Add a message to DM players with "msg: " followed by whatever.
        * Optional: Add up to five tags by using `~tag-name`.
        & <column 1> <column 2> ... [~tag-1 ~tag-2 ...] [msg: An optional message!]
        """
        if not is_admin(message.channel, message.author):
            await message.channel.send(s("not_admin"))
            return
        if not message.attachments:
            await message.channel.send(s("event_no_data"))
            return
        if not params:
            await message.channel.send(s("event_no_params"))
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
            await message.channel.send(s("tags_too_many"))
            return
        if opt_msg and len(opt_msg) >= 255:
            await message.channel.send(s("game_message_too_long"))
            return
        if not (1 < size <= 4):
            await message.channel.send(s("event_bad_play_count"))
            return
        if not attachment.filename.lower().endswith(".csv"):
            await message.channel.send(s("event_not_csv"))
            return

        tags = Tag.create_many(session, tag_names)

        bdata = await message.attachments[0].read()
        sdata = bdata.decode("utf-8")

        server = self.ensure_server_exists(session, message.channel.guild.id)
        reader = csv.reader(StringIO(sdata))
        header = [column.lower().strip() for column in next(reader)]
        params = [param.lower().strip() for param in params]

        if any(param not in header for param in params):
            await message.channel.send(s("event_no_header"))
            return

        columns = [header.index(param) for param in params]

        event = Event()
        session.add(event)
        session.commit()

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

            warnings = set()

            player_discord_users = []
            for csv_data, lname in zip(csv_row_data, player_lnames):
                player_discord_user = member_lookup.get(lname)
                if player_discord_user:
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

            warnings_s = "\n".join(warnings)
            for page in paginate(warnings_s):
                await message.channel.send(page)

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
                    await self.try_to_remove_plus(player_user.game, player_discord_user)
                    player_user.game_id = None
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

        if not event.games:
            session.delete(event)
            await message.channel.send(s("event_empty"))
            return

        session.commit()
        count = len([game for game in event.games])
        await message.channel.send(
            s("event_created", prefix=prefix, event_id=event.id, count=count)
        )

    @command(allow_dm=False)
    async def begin(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Confirm creation of games for the given event id. _Requires the
        "SpellBot Admin" role._
        & <event id>
        """
        if not is_admin(message.channel, message.author):
            await message.channel.send(s("not_admin"))
            return

        if not params:
            await message.channel.send(s("begin_no_params"))
            return

        event_id = to_int(params[0])
        if not event_id:
            await message.channel.send(s("begin_bad_event"))
            return

        event = session.query(Event).filter(Event.id == event_id).one_or_none()
        if not event:
            await message.channel.send(s("begin_bad_event"))
            return

        if event.started:
            await message.channel.send(s("begin_event_already_started"))
            return

        for game in event.games:
            # Can't rely on "<@{xid}>" working because the user could have logged out.
            sorted_names: List[str] = sorted([user.cached_name for user in game.users])
            players_str = ", ".join(sorted_names)

            found_discord_users = []
            for game_user in game.users:
                discord_user = await self.safe_fetch_user(game_user.xid)
                if not discord_user:  # game_user has left the server since event created
                    warning = s("begin_user_left", players=players_str)
                    await message.channel.send(warning)
                else:
                    found_discord_users.append(discord_user)
            if len(found_discord_users) != len(game.users):
                continue

            game.url = self.create_game() if game.system == "spelltable" else None
            game.status = "started"
            response = game.to_embed()
            for discord_user in found_discord_users:
                await discord_user.send(embed=response)

            session.commit()
            await message.channel.send(
                s("game_created", id=game.id, url=game.url, players=players_str)
            )

    @command(allow_dm=False)
    async def game(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Create a game between mentioned users. _Requires the "SpellBot Admin" role._

        Allows event runners to spin up an ad-hoc game directly between mentioned players.
        * The user who issues this command is **NOT** added to the game themselves.
        * You must mention all of the players to be seated in the game.
        * Optional: Add a message by using "msg: " followed by the message content.
        * Optional: Add tags by using "~tag-name" for the tags you want.
        & @player1 @player2 ... [~tag-1 ~tag-2] [msg: Hello world!]
        """
        if not is_admin(message.channel, message.author):
            await message.channel.send(s("not_admin"))
            return

        opts = parse_opts(params)
        size, tag_names, opt_msg, system = (
            opts["size"],
            opts["tags"],
            opts["message"],
            opts["system"],
        )
        mentions = message.mentions if message.channel.type != "private" else []

        if opt_msg and len(opt_msg) >= 255:
            await message.channel.send(s("game_message_too_long"))
            return
        if tag_names and len(tag_names) > 5:
            await message.channel.send(s("tags_too_many"))
            return

        if not size or not (1 < size <= 4):
            await message.channel.send(s("game_size_bad"))
            return

        if len(mentions) > size:
            await message.channel.send(s("game_too_many_mentions", size=size))
            return
        elif len(mentions) < size:
            await message.channel.send(s("game_too_few_mentions", size=size))
            return

        mentioned_users = []
        for mentioned in mentions:
            mentioned_user = self.ensure_user_exists(session, mentioned)
            if mentioned_user.waiting:
                await self.try_to_remove_plus(mentioned_user.game, mentioned)
                mentioned_user.game_id = None
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

        player_response = game.to_embed()
        for player in mentioned_users:
            discord_user = await self.safe_fetch_user(player.xid)
            # TODO: What happens if discord_user is None?
            if discord_user:
                await discord_user.send(embed=player_response)

        players_str = ", ".join(sorted([f"<@{user.xid}>" for user in mentioned_users]))
        await message.channel.send(
            s("game_created", id=game.id, url=game.url, players=players_str)
        )

    @command(allow_dm=True)
    async def leave(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Leave any pending game that you've signed up for on this server.
        """
        user = self.ensure_user_exists(session, message.author)
        if not user.waiting:
            await message.channel.send(s("leave_already"))
            return

        await self.try_to_remove_plus(user.game, cast(discord.User, message.author))

        user.game_id = None
        session.commit()
        await message.channel.send(s("leave"))

    @command(allow_dm=False)
    async def export(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Exports historical game data to a CSV file. _Requires the "SpellBot Admin" role._
        """
        if not is_admin(message.channel, message.author):
            await message.channel.send(s("not_admin"))
            return

        server = self.ensure_server_exists(session, message.channel.guild.id)
        export_file = TMP_DIR / f"{message.channel.guild.name}.csv"
        channel_name_cache = {}
        with open(export_file, "w") as f, redirect_stdout(f):
            print(  # noqa: T001
                "id,size,status,message,system,channel_xid,url,event_id,created_at,tags"
            )
            data = server.games_data()
            for i in range(len(data["id"])):
                channel_xid = data["channel_xid"][i]
                if channel_xid not in channel_name_cache:
                    channel = await self.safe_fetch_channel(int(channel_xid))
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
                            data["message"][i],
                            data["system"][i],
                            channel_name_cache[data["channel_xid"][i]],
                            data["url"][i],
                            data["event_id"][i],
                            data["created_at"][i],
                            data["tags"][i],
                        ]
                    )
                )
        await message.channel.send("", file=discord.File(export_file))

    @command(allow_dm=False)
    async def spellbot(
        self, session: Session, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Configure SpellBot for your server. _Requires the "SpellBot Admin" role._

        The following subcommands are supported:
        * `config`: Just show the current configuration for this server.
        * `channel <list>`: Set SpellBot to only respond in the given list of channels.
        * `prefix <string>`: Set SpellBot prefix for commands in text channels.
        * `expire <number>`: Set the number of minutes before pending games expire.
        & <subcommand> [subcommand parameters]
        """
        if not is_admin(message.channel, message.author):
            await message.channel.send(s("not_admin"))
            return
        if not params:
            await message.channel.send(s("spellbot_missing_subcommand"))
            return

        server = self.ensure_server_exists(session, message.channel.guild.id)

        command = params[0]
        if command == "channels":
            await self.spellbot_channels(session, server, params[1:], message)
        elif command == "prefix":
            await self.spellbot_prefix(session, server, params[1:], message)
        elif command == "expire":
            await self.spellbot_expire(session, server, params[1:], message)
        elif command == "config":
            await self.spellbot_config(session, server, params[1:], message)
        else:
            await message.channel.send(s("spellbot_unknown_subcommand", command=command))

    async def spellbot_channels(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await message.channel.send(s("spellbot_channels_none"))
            return

        # Blow away the current associations first, otherwise SQLAlchemy will explode.
        session.query(Channel).filter_by(guild_xid=server.guild_xid).delete()

        channels = []
        for param in params:
            m = re.match("<#([0-9]+)>", param)
            if not m:
                continue

            discord_channel = await self.safe_fetch_channel(int(m[1]))
            if not discord_channel:
                continue

            channel = Channel(channel_xid=discord_channel.id, guild_xid=server.guild_xid)
            session.add(channel)
            channels.append(channel)
            session.commit()

        if channels:
            server.channels = channels
            session.commit()
            channels_str = ", ".join([f"<#{c.channel_xid}>" for c in channels])
            await message.channel.send(s("spellbot_channels", channels=channels_str))

    async def spellbot_prefix(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await message.channel.send(s("spellbot_prefix_none"))
            return
        prefix_str = params[0][0:10]
        server.prefix = prefix_str
        session.commit()
        await message.channel.send(s("spellbot_prefix", prefix=prefix_str))
        return

    async def spellbot_expire(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await message.channel.send(s("spellbot_expire_none"))
            return
        expire = to_int(params[0])
        if not expire or not (0 < expire <= 60):
            await message.channel.send(s("spellbot_expire_bad"))
            return
        server = (
            session.query(Server)
            .filter(Server.guild_xid == message.channel.guild.id)
            .one_or_none()
        )
        server.expire = expire
        session.commit()
        await message.channel.send(s("spellbot_expire", expire=expire))

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
        embed.color = discord.Color(0x5A3EFD)
        embed.set_footer(text=f"Config for Guild ID: {server.guild_xid}")
        await message.channel.send(embed=embed)


def get_db_env(fallback: str) -> str:  # pragma: no cover
    """Returns the database env var from the environment or else the given gallback."""
    value = getenv("SPELLBOT_DB_ENV", fallback)
    return value or fallback


def get_db_url(database_env: str, fallback: str) -> str:  # pragma: no cover
    """Returns the database url from the environment or else the given fallback."""
    value = getenv(database_env, fallback)
    return value or fallback


def get_log_level(fallback: str) -> str:  # pragma: no cover
    """Returns the log level from the environment or else the given gallback."""
    value = getenv("SPELLBOT_LOG_LEVEL", fallback)
    return value or fallback


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
    dev: bool,
    mock_games: bool,
) -> None:  # pragma: no cover
    database_env = get_db_env(database_env)
    database_url = get_db_url(database_env, database_url)
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

    client = SpellBot(
        token=token,
        auth=auth,
        db_url=database_url,
        log_level="DEBUG" if verbose else log_level,
        mock_games=mock_games,
    )

    if dev:
        reloader = hupper.start_reloader("spellbot.main")
        reloader.watch_files(ASSET_FILES)

    client.run()


if __name__ == "__main__":
    main()
