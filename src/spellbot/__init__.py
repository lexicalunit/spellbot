import asyncio
import csv
import inspect
import logging
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import wraps
from io import StringIO
from os import getenv
from pathlib import Path
from uuid import uuid4

import click
import discord
import hupper
import requests
from sqlalchemy import exc
from sqlalchemy.sql import text

from spellbot._version import __version__
from spellbot.assets import ASSET_FILES, s
from spellbot.constants import ADMIN_ROLE, CREATE_ENDPOINT, THUMB_URL
from spellbot.data import Channel, Data, Event, Game, Server, Tag, User

# Application Paths
RUNTIME_ROOT = Path(".")
SCRIPTS_DIR = RUNTIME_ROOT / "scripts"
DB_DIR = RUNTIME_ROOT / "db"
DEFAULT_DB_URL = f"sqlite:///{DB_DIR}/spellbot.db"
TMP_DIR = RUNTIME_ROOT / "tmp"
MIGRATIONS_DIR = SCRIPTS_DIR / "migrations"


def to_int(s):
    try:
        return int(s)
    except ValueError:
        return None


def size_from_params(params):
    size = 4
    for param in params:
        if param.startswith("size:"):
            size = to_int(param.replace("size:", ""))
    return size


def tag_names_from_params(params):
    tag_names = [
        param
        for param in params
        if not param.startswith("size:")
        and not param.startswith("<")
        and not param.startswith("@")
        and not len(param) >= 50
    ]
    if not tag_names:
        tag_names = ["default"]
    return tag_names


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


def paginate(text):
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
        mock_games=False,
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
    async def session(self):  # pragma: no cover
        session = self.data.Session()
        try:
            yield session
        except exc.SQLAlchemyError as e:
            logging.exception("database error:", e)
            session.rollback()
            raise
        finally:
            session.close()

    async def safe_fetch_message(self, channel, message_xid):  # pragma: no cover
        try:
            return await channel.fetch_message(message_xid)
        except (
            discord.errors.HTTPException,
            discord.errors.NotFound,
            discord.errors.Forbidden,
        ) as e:
            logging.exception("warning: discord: could not fetch message", e)

    async def safe_fetch_channel(self, channel_xid):  # pragma: no cover
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

    async def safe_fetch_user(self, user_xid):  # pragma: no cover
        user = self.get_user(user_xid)
        if user:
            return user
        try:
            return await self.fetch_user(user_xid)
        except (discord.errors.NotFound, discord.errors.HTTPException,) as e:
            logging.exception("warning: discord: could fetch user", e)

    async def safe_remove_reaction(self, message, emoji, user):  # pragma: no cover
        try:
            await message.remove_reaction(emoji, user)
        except (
            discord.errors.HTTPException,
            discord.errors.Forbidden,
            discord.errors.NotFound,
            discord.errors.InvalidArgument,
        ) as e:
            logging.exception("warning: discord: could not remove reaction", e)

    async def safe_clear_reactions(self, message):  # pragma: no cover
        try:
            await message.clear_reactions()
        except (discord.errors.HTTPException, discord.errors.Forbidden,) as e:
            logging.exception("warning: discord: could not clear reactions", e)

    async def safe_edit_message(
        self, message, *, reason=None, **options
    ):  # pragma: no cover
        try:
            await message.edit(reason=reason, **options)
        except (
            discord.errors.InvalidArgument,
            discord.errors.Forbidden,
            discord.errors.HTTPException,
        ) as e:
            logging.exception("warning: discord: could not edit message", e)

    async def safe_delete_message(self, message):  # pragma: no cover
        try:
            await message.delete()
        except (
            discord.errors.Forbidden,
            discord.errors.NotFound,
            discord.errors.HTTPException,
        ) as e:
            logging.exception("warning: discord: could not delete message", e)

    def _begin_background_tasks(self, loop):  # pragma: no cover
        """Start up any periodic background tasks."""
        self.cleanup_expired_games_task(loop)
        self.cleanup_started_games_task(loop)

    def cleanup_expired_games_task(self, loop):  # pragma: no cover
        """Starts a task that culls old games."""
        THIRTY_SECONDS = 30

        async def task():
            while True:
                await asyncio.sleep(THIRTY_SECONDS)
                await self.cleanup_expired_games()

        loop.create_task(task())

    async def cleanup_expired_games(self):
        """Culls games older than the given window of minutes."""
        async with self.session() as session:
            expired = Game.expired(session)
            for game in expired:
                await self.try_to_delete_message(game)
                for user in game.users:
                    discord_user = await self.safe_fetch_user(user.xid)
                    if discord_user:
                        await discord_user.send(s("expired", window=game.server.expire))
                    user.game = None
                game.tags = []  # cascade delete tag associations
                session.delete(game)
            session.commit()

    def cleanup_started_games_task(self, loop):  # pragma: no cover
        """Starts a task that culls old games."""
        FOUR_HOURS = 14400

        async def task():
            while True:
                await asyncio.sleep(FOUR_HOURS)
                await self.cleanup_started_games()

        loop.create_task(task())

    async def cleanup_started_games(self):
        """Culls games older than the given window of minutes."""
        async with self.session() as session:
            games = session.query(Game).filter(Game.status == "started").all()
            for game in games:
                game.tags = []  # cascade delete tag associations
                session.delete(game)
            session.commit()

    def run(self):  # pragma: no cover
        super().run(self.token)

    def create_game(self):  # pragma: no cover
        if self.mock_games:
            return f"http://exmaple.com/game/{uuid4()}"
        else:
            headers = {"user-agent": f"spellbot/{__version__}", "key": self.auth}
            r = requests.post(CREATE_ENDPOINT, headers=headers)
            return r.json()["gameUrl"]

    def ensure_user_exists(self, session, user):
        """Ensures that the user row exists for the given discord user."""
        db_user = session.query(User).filter(User.xid == user.id).one_or_none()
        if not db_user:
            db_user = User(xid=user.id)
            session.add(db_user)
        return db_user

    def ensure_server_exists(self, session, guild_xid):
        """Ensures that the server row exists for the given discord guild id."""
        server = session.query(Server).filter(Server.guild_xid == guild_xid).one_or_none()
        if not server:
            server = Server(guild_xid=guild_xid)
            session.add(server)
        return server

    async def try_to_delete_message(self, game):
        """Attempts to remove a ➕ from the given game message for the given user."""
        chan = await self.safe_fetch_channel(game.channel_xid)
        if not chan:
            return

        post = await self.safe_fetch_message(chan, game.message_xid)
        if not post:
            return

        await self.safe_delete_message(post)

    async def try_to_remove_plus(self, game, discord_user):
        """Attempts to remove a ➕ from the given game message for the given user."""
        chan = await self.safe_fetch_channel(game.channel_xid)
        if not chan:
            return

        post = await self.safe_fetch_message(chan, game.message_xid)
        if not post:
            return

        await self.safe_remove_reaction(post, "➕", discord_user)

    @property
    def commands(self):
        """Returns a list of commands supported by this bot."""
        return self._commands

    async def process(self, message, prefix):
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
        else:
            command = request if request in matching else matching[0]
            method = getattr(self, command)
            if not method.allow_dm and str(message.channel.type) == "private":
                return await message.author.send(s("no_dm"))
            logging.debug(
                "%s%s (params=%s, message=%s)", prefix, command, params, message
            )
            async with self.session() as session:
                await method(session, prefix, params, message)

    ##############################
    # Discord Client Behavior
    ##############################

    async def on_raw_reaction_add(self, payload):
        """Behavior when the client gets a new reaction on a Discord message."""
        emoji = str(payload.emoji)
        if emoji not in ["➕", "➖"]:
            return

        channel = await self.safe_fetch_channel(payload.channel_id)
        if not channel or str(channel.type) != "text":
            return

        author = payload.member
        if author.bot or author.id == self.user.id:
            return

        message = await self.safe_fetch_message(channel, payload.message_id)
        if not message:
            return

        async with self.session() as session:
            server = self.ensure_server_exists(session, payload.guild_id)
            session.commit()

            if not server.bot_allowed_in(channel.name):
                return

            game = (
                session.query(Game).filter(Game.message_xid == message.id).one_or_none()
            )
            if not game or game.status != "pending":
                return  # this isn't a post relating to a game, just ignore it

            user = self.ensure_user_exists(session, author)
            session.commit()

            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=server.expire)

            await self.safe_remove_reaction(message, emoji, author)

            if emoji == "➕":
                if any(user.xid == game_user.xid for game_user in game.users):
                    # this author is already in this game, they don't need to be added
                    return
                if user.game and user.game.id != game.id:
                    # this author is already another game, they can't be added
                    return await author.send(s("react_already_in", prefix=server.prefix))
                user.game = game
            else:  # emoji == "➖":
                if not any(user.xid == game_user.xid for game_user in game.users):
                    # this author is not in this game, so they can't be removed from it
                    return

                # update the game and remove the user from the game
                game.updated_at = now
                game.expires_at = expires_at
                user.game = None
                session.commit()

                # update the game message
                return await self.safe_edit_message(message, embed=game.to_embed())

            game.updated_at = now
            game.expires_at = expires_at
            session.commit()

            found_discord_users = []
            if len(game.users) == game.size:
                for game_user in game.users:
                    discord_user = await self.safe_fetch_user(game_user.xid)
                    if not discord_user:  # user has left the server since signing up
                        game_user.game = None
                        obj = discord.Object(game_user.xid)
                        await self.safe_remove_reaction(message, "➕", obj)
                    else:
                        found_discord_users.append(discord_user)

            if len(found_discord_users) == game.size:  # game is ready
                game.url = self.create_game()
                game.status = "started"
                session.commit()
                for discord_user in found_discord_users:
                    await discord_user.send(embed=game.to_embed())
                await self.safe_edit_message(message, embed=game.to_embed())
                await self.safe_clear_reactions(message)
            else:
                session.commit()
                await self.safe_edit_message(message, embed=game.to_embed())

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
                session.commit()
                if not server.bot_allowed_in(message.channel.name):
                    return

        await self.process(message, prefix)

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
    async def help(self, session, prefix, params, message):
        """
        Sends you this help message.
        """
        usage = ""
        for command in self.commands:
            method = getattr(self, command)
            doc = method.__doc__.split("&")
            use, params = doc[0], ", ".join([param.strip() for param in doc[1:]])
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
            if params:
                title = f"{title} {params}"
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
    async def about(self, session, prefix, params, message):
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
    async def lfg(self, session, prefix, params, message):
        """
        Create a pending game for players to join.

        The default game size is 4 but you can change it by adding, for example, `size:2`
        to create a two player game.

        Players will be able to join or leave the game by reacting to the message that
        SpellBot sends with the ➕ and ➖ emoji.

        Up to five tags can be given as well to help describe the game expereince that you
        want. For example you might send `!lfg no-combo proxy` which will assign the tags:
        `no-combo` and `proxy` to your game. People will be able to see what tags are set
        on your game when they are looking for games to join.
        & [size:N] [tag-1] [tag-2] [...] [tag-N]
        """
        server = self.ensure_server_exists(session, message.channel.guild.id)
        session.commit()

        user = self.ensure_user_exists(session, message.author)
        if user.waiting:
            return await message.channel.send(s("lfg_already", prefix=server.prefix))

        params = [param.lower() for param in params]

        size = size_from_params(params)
        if not size or not (1 < size < 5):
            return await message.channel.send(s("lfg_size_bad"))

        tag_names = tag_names_from_params(params)
        if len(tag_names) > 5:
            return await message.channel.send(s("lfg_too_many_tags"))

        tags = []
        for tag_name in tag_names:
            tag = session.query(Tag).filter_by(name=tag_name).one_or_none()
            if not tag:
                tag = Tag(name=tag_name)
                session.add(tag)
            tags.append(tag)

        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=server.expire)
        user.game = Game(
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            size=size,
            channel_xid=message.channel.id,
            tags=tags,
            server=server,
        )
        session.commit()

        post = await message.channel.send(embed=user.game.to_embed())
        user.game.message_xid = post.id
        session.commit()

        await post.add_reaction("➕")
        await post.add_reaction("➖")

    @command(allow_dm=False)
    async def event(self, session, prefix, params, message):
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
        * Optional: Add a message by using " -- " followed by the message content.
        & <column 1> <column 2> ... <column 3> [-- An optional message to add.]
        """
        if not is_admin(message.channel, message.author):
            return await message.channel.send(s("not_admin"))

        if not message.attachments:
            return await message.channel.send(s("event_no_data"))

        if not params:
            return await message.channel.send(s("event_no_params"))

        optional_message = None
        try:
            sentry = params.index("--")
            optional_message = " ".join(params[sentry + 1 :])
            params = params[0:sentry]
        except ValueError:
            pass

        if optional_message and len(optional_message) >= 255:
            return await message.channel.send(s("game_message_too_long"))

        size = len(params)
        if not (1 < size <= 4):
            return await message.channel.send(s("event_bad_play_count"))

        attachment = message.attachments[0]

        if not attachment.filename.lower().endswith(".csv"):
            return await message.channel.send(s("event_not_csv"))

        bdata = await message.attachments[0].read()
        sdata = bdata.decode("utf-8")

        has_header = csv.Sniffer().has_header(sdata)
        if not has_header:
            return await message.channel.send(s("event_no_header"))

        server = self.ensure_server_exists(session, message.channel.guild.id)
        reader = csv.reader(StringIO(sdata))
        header = [column.lower().strip() for column in next(reader)]
        params = [param.lower().strip() for param in params]

        if any(param not in header for param in params):
            return await message.channel.send(s("event_no_header"))

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

            player_discord_users = []
            for csv_data, lname in zip(csv_row_data, player_lnames):
                player_discord_user = member_lookup.get(lname)
                if player_discord_user:
                    player_discord_users.append(player_discord_user)
                else:
                    warning = s(
                        "event_missing_user", row=i + 1, name=csv_data, players=players_s,
                    )
                    await message.channel.send(warning)

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
                    player_user.game = None
                player_user.cached_name = player_discord_user.name
            session.commit()

            tag = session.query(Tag).filter_by(name="default").one_or_none()
            if not tag:
                tag = Tag(name="default")
                session.add(tag)
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
                message=optional_message,
                users=player_users,
                event=event,
                tags=[tag],
            )
            session.add(game)
            session.commit()

        if not event.games:
            session.delete(event)
            return await message.channel.send(s("event_empty"))

        session.commit()
        await message.channel.send(s("event_created", prefix=prefix, event_id=event.id))

    @command(allow_dm=False)
    async def begin(self, session, prefix, params, message):
        """
        Confirm creation of games for the given event id. _Requires the
        "SpellBot Admin" role._
        & <event id>
        """
        if not is_admin(message.channel, message.author):
            return await message.channel.send(s("not_admin"))

        if not params:
            return await message.channel.send(s("begin_no_params"))

        event_id = to_int(params[0])
        if not event_id:
            return await message.channel.send(s("begin_bad_event"))

        event = session.query(Event).filter(Event.id == event_id).one_or_none()
        if not event:
            return await message.channel.send(s("begin_bad_event"))

        if event.started:
            return await message.channel.send(s("begin_event_already_started"))

        for game in event.games:
            # Can't rely on "<@{xid}>" working because the user could have logged out.
            players_str = ", ".join(sorted([user.cached_name for user in game.users]))

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

            game.url = self.create_game()
            game.status = "started"
            response = game.to_embed()
            for discord_user in found_discord_users:
                await discord_user.send(embed=response)

            session.commit()
            await message.channel.send(
                s("game_created", id=game.id, url=game.url, players=players_str)
            )

    @command(allow_dm=False)
    async def game(self, session, prefix, params, message):
        """
        Create a game between mentioned users. _Requires the "SpellBot Admin" role._

        Operates similarly to the `!lfg` command with a few key deferences. First, see
        that command's usage help for more details. Then, here are the differences:
        * The user who issues this command is **NOT** added to the game themselves.
        * You must mention all of the players to be seated in the game.
        * Optional: Add a message by using " -- " followed by the message content.
        & [similar parameters as !lfg] [-- An optional additional message to send.]
        """
        if not is_admin(message.channel, message.author):
            return await message.channel.send(s("not_admin"))

        optional_message = None
        try:
            sentry = params.index("--")
            optional_message = " ".join(params[sentry + 1 :])
            params = params[0:sentry]
        except ValueError:
            pass

        if optional_message and len(optional_message) >= 255:
            return await message.channel.send(s("game_message_too_long"))

        params = [param.lower() for param in params]
        mentions = message.mentions if message.channel.type != "private" else []

        size = size_from_params(params)
        if not size or not (1 < size <= 4):
            return await message.channel.send(s("game_size_bad"))

        if len(mentions) > size:
            return await message.channel.send(s("game_too_many_mentions", size=size))
        elif len(mentions) < size:
            return await message.channel.send(s("game_too_few_mentions", size=size))

        mentioned_users = []
        for mentioned in mentions:
            mentioned_user = self.ensure_user_exists(session, mentioned)
            if mentioned_user.waiting:
                await self.try_to_remove_plus(mentioned_user.game, mentioned)
                mentioned_user.game = None
            mentioned_users.append(mentioned_user)
        session.commit()

        tag_names = tag_names_from_params(params)
        if len(tag_names) > 5:
            return await message.channel.send(s("game_too_many_tags"))

        tags = []
        for tag_name in tag_names:
            tag = session.query(Tag).filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                session.add(tag)
            tags.append(tag)

        server = self.ensure_server_exists(session, message.channel.guild.id)
        session.commit()

        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=server.expire)
        url = self.create_game()
        game = Game(
            channel_xid=message.channel.id,
            created_at=now,
            expires_at=expires_at,
            guild_xid=server.guild_xid,
            size=size,
            updated_at=now,
            url=url,
            status="started",
            message=optional_message,
            users=mentioned_users,
            tags=tags,
        )
        session.add(game)
        session.commit()

        player_response = game.to_embed()
        for player in mentioned_users:
            discord_user = await self.safe_fetch_user(player.xid)
            await discord_user.send(embed=player_response)

        players_str = ", ".join(sorted([f"<@{user.xid}>" for user in mentioned_users]))
        await message.channel.send(
            s("game_created", id=game.id, url=game.url, players=players_str)
        )

    @command(allow_dm=True)
    async def leave(self, session, prefix, params, message):
        """
        Leave any pending game that you've signed up for on this server.
        """
        user = self.ensure_user_exists(session, message.author)
        if not user.waiting:
            return await message.channel.send(s("leave_already"))

        await self.try_to_remove_plus(user.game, message.author)

        user.game = None
        session.commit()
        await message.channel.send(s("leave"))

    @command(allow_dm=False)
    async def spellbot(self, session, prefix, params, message):
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
            return await message.channel.send(s("not_admin"))
        if not params:
            return await message.channel.send(s("spellbot_missing_subcommand"))

        self.ensure_server_exists(session, message.channel.guild.id)
        command = params[0]
        if command == "channels":
            await self.spellbot_channels(session, prefix, params[1:], message)
        elif command == "prefix":
            await self.spellbot_prefix(session, prefix, params[1:], message)
        elif command == "expire":
            await self.spellbot_expire(session, prefix, params[1:], message)
        elif command == "config":
            await self.spellbot_config(session, prefix, params[1:], message)
        else:
            await message.channel.send(s("spellbot_unknown_subcommand", command=command))

    async def spellbot_channels(self, session, prefix, params, message):
        if not params:
            return await message.channel.send(s("spellbot_channels_none"))
        session.query(Channel).filter_by(guild_xid=message.channel.guild.id).delete()
        for param in params:
            session.add(Channel(guild_xid=message.channel.guild.id, name=param))
        session.commit()
        await message.channel.send(
            s("spellbot_channels", channels=", ".join([f"#{param}" for param in params]))
        )

    async def spellbot_prefix(self, session, prefix, params, message):
        if not params:
            return await message.channel.send(s("spellbot_prefix_none"))
        prefix_str = params[0][0:10]
        server = (
            session.query(Server)
            .filter(Server.guild_xid == message.channel.guild.id)
            .one_or_none()
        )
        server.prefix = prefix_str
        session.commit()
        return await message.channel.send(s("spellbot_prefix", prefix=prefix_str))

    async def spellbot_expire(self, session, prefix, params, message):
        if not params:
            return await message.channel.send(s("spellbot_expire_none"))
        expire = to_int(params[0])
        if not expire or not (0 < expire <= 60):
            return await message.channel.send(s("spellbot_expire_bad"))
        server = (
            session.query(Server)
            .filter(Server.guild_xid == message.channel.guild.id)
            .one_or_none()
        )
        server.expire = expire
        session.commit()
        await message.channel.send(s("spellbot_expire", expire=expire))

    async def spellbot_config(self, session, prefix, params, message):
        server = (
            session.query(Server)
            .filter(Server.guild_xid == message.channel.guild.id)
            .one_or_none()
        )
        embed = discord.Embed(title="SpellBot Server Config")
        embed.set_thumbnail(url=THUMB_URL)
        embed.add_field(name="Command prefix", value=server.prefix)
        expires_str = f"{server.expire} minutes"
        embed.add_field(name="Inactivity expiration time", value=expires_str)
        channels = server.channels
        if channels:
            channels_str = ", ".join(f"#{channel.name}" for channel in channels)
        else:
            channels_str = "all"
        embed.add_field(name="Authorized channels", value=channels_str)
        embed.color = discord.Color(0x5A3EFD)
        embed.set_footer(text=f"Config for Guild ID: {server.guild_xid}")
        await message.channel.send(embed=embed)


def get_db_env(fallback):  # pragma: no cover
    """Returns the database env var from the environment or else the given gallback."""
    value = getenv("SPELLTABLE_DB_ENV", fallback)
    return value or fallback


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
    help="Can also be set by the environment variable SPELLTABLE_LOG_LEVEL.",
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
        "Can also be set by the environment variable SPELLTABLE_DB_ENV."
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
    log_level, verbose, database_url, database_env, dev, mock_games
):  # pragma: no cover
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
