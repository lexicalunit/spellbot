import asyncio
import csv
import inspect
import logging
import math
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
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Union,
    cast,
)
from urllib import parse
from uuid import uuid4

import click
import coloredlogs  # type: ignore
import discord
import discord.errors
import hupper  # type: ignore
import redis
import requests
from aiohttp import web
from aiohttp.web_response import Response
from dotenv import load_dotenv
from expiringdict import ExpiringDict  # type: ignore
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from sqlalchemy import exc
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import text
from sqlalchemy.sql.expression import and_

from spellbot._version import __version__
from spellbot.assets import ASSET_FILES, s
from spellbot.constants import (
    ADMIN_ROLE,
    CLEAN_S,
    CREATE_ENDPOINT,
    DEFAULT_GAME_SIZE,
    EMOJI_DROP_GAME,
    EMOJI_JOIN_GAME,
    ICO_URL,
    INVITE_LINK,
    THUMB_URL,
    VOICE_CATEGORY_PREFIX,
    VOICE_INVITE_EXPIRE_TIME_S,
    VOTE_LINK,
)
from spellbot.data import (
    AutoVerifyChannel,
    Award,
    Channel,
    ChannelSettings,
    Data,
    Event,
    Game,
    Metric,
    Play,
    Report,
    Server,
    Tag,
    Team,
    UnverifiedOnlyChannel,
    User,
    UserAward,
    UserPoints,
    UserServerSettings,
    WatchedUser,
    users_blocks,
)
from spellbot.operations import (
    MentionableChannelType,
    safe_clear_reactions,
    safe_create_category_channel,
    safe_create_invite,
    safe_create_voice_channel,
    safe_delete_message,
    safe_edit_message,
    safe_fetch_channel,
    safe_fetch_guild,
    safe_fetch_message,
    safe_fetch_user,
    safe_react_emoji,
    safe_react_error,
    safe_react_ok,
    safe_remove_reaction,
    safe_send_channel,
    safe_send_user,
)
from spellbot.tasks import begin_background_tasks

if not getenv("PYTEST_CURRENT_TEST") and "pytest" not in sys.modules:
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


def playedh_log(message: discord.Message, s: str) -> None:  # pragma: no cover
    """Useful to introduce PlayEDH specific debug logging."""
    if message.channel.guild.id != 304276578005942272:
        return
    logger.error(f"playedh: {message.channel.name}: {s}")


def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def parse_opts(params: List[str], default_size: Optional[int] = None) -> dict:
    tags: List[str] = []
    first_pass: List[str] = []
    second_pass: List[str] = []
    size: Optional[int] = default_size or DEFAULT_GAME_SIZE
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
    channel: discord.TextChannel, user_or_member: Union[discord.User, discord.Member]
) -> bool:
    """Checks to see if given user or member has the admin role on this server."""
    member = (
        user_or_member
        if hasattr(user_or_member, "roles")
        else channel.guild.get_member(cast(discord.User, user_or_member).id)
    )
    if not member or not hasattr(member, "roles"):
        return False
    roles = cast(List[discord.Role], cast(discord.Member, member).roles)
    return any(role.name == ADMIN_ROLE for role in roles) if member else False


async def check_is_admin(message: discord.Message) -> bool:
    """Checks if author of message is admin, alert the channel if they are not."""
    if not is_admin(message.channel, message.author):
        await safe_send_channel(
            message.channel, s("not_admin", reply=message.author.mention)
        )
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


def create_member_finder(message: discord.Message):
    class MemberFinder:
        def __init__(self, message: discord.Message):
            self.members = message.channel.guild.members
            self.FIND_MEMBER_CACHE: Dict[str, discord.User] = {}

        # find users by name using members intents
        def find(self, query: str) -> Optional[discord.User]:
            lowercase_name = re.sub("#.*$", "", query.lower()).lstrip("@")
            if lowercase_name in self.FIND_MEMBER_CACHE:
                return self.FIND_MEMBER_CACHE[lowercase_name]
            found_user = discord.utils.find(
                lambda m: m.name.lower() == lowercase_name
                or (m.nick is not None and m.nick.lower() == lowercase_name),
                self.members,
            )
            if found_user:
                self.FIND_MEMBER_CACHE[lowercase_name] = found_user
            return found_user

    return MemberFinder(message)


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
        redis_url: Optional[str] = None,
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
        intents = discord.Intents().default()
        intents.members = True
        super().__init__(loop=loop, intents=intents)
        self.token = token or ""
        self.auth = auth or ""
        self.mock_games = mock_games
        self.channel_lock_cache = ExpiringDict(max_len=100, max_age_seconds=3600)  # 1 hr
        self.average_wait_times: Dict[str, float] = {}

        # Connect to Redis Cloud if we have a URL for it.
        self.metrics_db = self._create_metrics_db(redis_url)

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

        # build a list of admin subcommands supported by this bot
        members = inspect.getmembers(self, predicate=inspect.ismethod)
        self._subcommands = [
            member[0][9:] for member in members if member[0].startswith("spellbot_")
        ]

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

    @asynccontextmanager
    async def channel_lock(self, channel_xid: int) -> AsyncGenerator[None, None]:
        """Aquire an async lock based on the given channel id."""
        lock = self.channel_lock_cache.get(channel_xid, asyncio.Lock())
        self.channel_lock_cache[channel_xid] = lock
        async with lock:  # type: ignore
            yield

    def _create_metrics_db(
        self, redis_url: Optional[str]
    ) -> Optional[redis.Redis]:  # pragma: no cover
        if not redis_url:
            return None

        url = parse.urlparse(redis_url)
        if url.hostname and url.port:
            try:
                return redis.Redis(  # type: ignore
                    host=url.hostname,
                    port=url.port,
                    password=url.password,
                    health_check_interval=30,  # type: ignore
                )
            except redis.exceptions.RedisError as e:
                logger.exception("redis error: %s", e)
        return None

    async def average_wait(self, session: Session, game: Game) -> Optional[float]:
        server = self.ensure_server_exists(session, game.guild_xid)
        if game.channel_xid is None:  # pragma: no cover
            return None
        channel_settings = self.ensure_channel_settings_exists(
            session, server, game.channel_xid
        )
        queue_time_enabled = (
            channel_settings.queue_time_enabled
            if channel_settings.queue_time_enabled is not None
            else server.queue_time_enabled
        )
        if not queue_time_enabled:
            return None
        return self.average_wait_times.get(f"{game.guild_xid}-{game.channel_xid}")

    @property
    def commands(self) -> List[str]:
        """Returns the list of commands supported by this bot."""
        return self._commands

    @property
    def subcommands(self) -> List[str]:
        """Returns the list of subcommands that can be given to the !spellbot command."""
        return self._subcommands

    def run(self) -> None:  # pragma: no cover
        super().run(self.token)

    async def send_watch_list_notifications(self, session: Session, game: Game) -> None:
        if not game.channel_xid or not game.message_xid:
            return

        watched = (
            session.query(WatchedUser)
            .filter(
                and_(
                    WatchedUser.guild_xid == game.guild_xid,
                    WatchedUser.user_xid.in_([user.xid for user in game.users]),
                )
            )
            .all()
        )
        if not watched:
            return

        guild = await safe_fetch_guild(self, game.guild_xid)
        if not guild:
            return

        mod_role: Optional[discord.Role] = None
        for role in guild.roles:
            if role.name == "Moderators":
                mod_role = role
                break
        if not mod_role:
            return

        link = post_link(game.guild_xid, game.channel_xid, game.message_xid)
        notification_message = s(
            "watched_user_notification",
            game_id=game.id,
            users=", ".join(f"<@{w.user_xid}> ({w.note})" for w in watched),
            link=link,
        )
        for mod in mod_role.members:
            await safe_send_user(mod, notification_message)

    def create_spelltable_url(self) -> Optional[str]:
        if self.mock_games:
            return f"http://exmaple.com/game/{uuid4()}"

        headers = {"user-agent": f"spellbot/{__version__}", "key": self.auth}
        r = requests_retry_session().post(CREATE_ENDPOINT, headers=headers, timeout=5)
        try:
            return cast(str, r.json()["gameUrl"])
        except KeyError as e:
            logger.error(
                "error: gameUrl missing from SpellTable API response (%s): %s; %s",
                r.status_code,
                r.json(),
                e,
            )
        except (ValueError, TypeError) as e:
            logger.error(
                "error: non-JSON response from SpellTable API response (%s): %s; %s",
                r.status_code,
                r.content,
                e,
            )
        return None

    async def setup_voice(
        self, session: Session, game: Game, prefix: str = VOICE_CATEGORY_PREFIX
    ) -> None:
        """Adds voice information to the game object. DOES NOT COMMIT!"""
        # NOTE: See the test_simultaneous_signup() test for more details about
        #       how this function has caused issues in the past.
        if not game.server.create_voice or game.voice_channel_xid:
            return

        category = await self.ensure_available_voice_category(game.server, prefix)

        # if category is None, then we'll simply create a non-categorized channel
        voice_channel = await safe_create_voice_channel(
            self, game.server.guild_xid, f"Game-SB{game.id}", category=category
        )

        if voice_channel:
            game.voice_channel_xid = voice_channel.id  # type: ignore

            voice_invite = await safe_create_invite(
                voice_channel, game.guild_xid, max_age=VOICE_INVITE_EXPIRE_TIME_S
            )
            if voice_invite:
                game.voice_channel_invite = voice_invite  # type: ignore

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
            db_user.name = cast(Any, user).name  # type: ignore
            db_user.updated_at = datetime.utcnow()  # type: ignore
        session.commit()
        return cast(User, db_user)

    def ensure_user_award_exists(
        self, session: Session, user_xid: int, guild_xid: int
    ) -> UserAward:
        """Ensures that the user award row exists for the given ids."""
        user_award = (
            session.query(UserAward)
            .filter(
                and_(UserAward.user_xid == user_xid, UserAward.guild_xid == guild_xid)
            )
            .one_or_none()
        )
        if not user_award:
            user_award = UserAward(user_xid=user_xid, guild_xid=guild_xid)
            session.add(user_award)
            session.commit()
        return cast(UserAward, user_award)

    def ensure_user_settings_exists(
        self, session: Session, user: User, server: Server
    ) -> UserServerSettings:
        """Ensures that a user has server settings for the given user and guild."""
        user_settings = (
            session.query(UserServerSettings)
            .filter_by(user_xid=user.xid, guild_xid=server.guild_xid)
            .one_or_none()
        )
        if not user_settings:
            user_settings = UserServerSettings(
                user_xid=user.xid, guild_xid=server.guild_xid
            )
            session.add(user_settings)
            session.commit()
        return cast(UserServerSettings, user_settings)

    def ensure_server_exists(self, session: Session, guild_xid: int) -> Server:
        """Ensures that the server row exists for the given discord guild id."""
        server = session.query(Server).filter(Server.guild_xid == guild_xid).one_or_none()
        if not server:
            server = Server(guild_xid=guild_xid)
            session.add(server)
            session.commit()
        return cast(Server, server)

    def ensure_channel_settings_exists(
        self,
        session: Session,
        server: Server,
        channel_xid: int,
        channel_name: Optional[str] = None,
    ) -> ChannelSettings:
        """Ensures that the channel settings row exists for the given guild/channel id."""
        channel_settings = (
            session.query(ChannelSettings)
            .filter(
                and_(
                    ChannelSettings.guild_xid == server.guild_xid,
                    ChannelSettings.channel_xid == channel_xid,
                )
            )
            .one_or_none()
        )
        if not channel_settings:
            channel_settings = ChannelSettings(
                guild_xid=server.guild_xid,
                channel_xid=channel_xid,
                cached_name=channel_name,
            )
            session.add(channel_settings)
        else:
            if channel_name is not None and channel_name != "":
                channel_settings.cached_name = channel_name  # type: ignore
            channel_settings.updated_at = datetime.utcnow()  # type: ignore
        session.commit()
        return cast(ChannelSettings, channel_settings)

    async def ensure_available_voice_category(
        self, server: Server, prefix: str
    ) -> Optional[discord.CategoryChannel]:
        if not server.create_voice:
            return None

        guild = await safe_fetch_guild(self, server.guild_xid)
        if not guild:
            return None

        def category_num(cat: discord.CategoryChannel) -> int:
            return 0 if cat.name == prefix else int(cat.name[24:]) - 1

        def category_name(i: int) -> str:
            return prefix if i == 0 else f"{prefix} {i + 1}"

        available: Optional[discord.CategoryChannel] = None
        full: List[discord.CategoryChannel] = []
        for i, cat in enumerate(
            sorted(
                (c for c in guild.categories if c.name.startswith(prefix)),
                key=category_num,
            )
        ):
            if i != category_num(cat):
                break  # there's a missing category, we need to re-create it
            if len(cat.channels) < 50:
                available = cat
                break  # we found an available channel, use it
            else:
                full.append(cat)  # keep track of how many full channels there are

        if available:
            return cast(discord.CategoryChannel, available)

        category = await safe_create_category_channel(
            self, server.guild_xid, category_name(len(full))
        )
        if not category:
            return None

        return cast(discord.CategoryChannel, category)

    async def try_to_delete_message(
        self, guild_xid: int, channel_xid: int, message_xid: int
    ) -> None:
        """Try to remove reactions from game post and replace with a "deleted" message."""
        chan = await safe_fetch_channel(self, channel_xid, guild_xid)
        if not chan:
            return

        post = await safe_fetch_message(chan, message_xid, guild_xid)
        if not post:
            return

        # NOTE: Deleting the whole post ended up being confusing by invalidating
        #       hyperlinks to game posts. Instead, let's just empty the post contents.
        # await safe_delete_message(post)
        await safe_edit_message(post, content=s("deleted_game"), embed=None)
        await safe_clear_reactions(post)

    async def try_to_update_game(self, session: Session, game: Game) -> None:
        """Attempts to update the embed for a game."""
        if not game.channel_xid or not game.message_xid:
            return

        chan = await safe_fetch_channel(self, game.channel_xid, game.guild_xid)
        if not chan:
            return

        post = await safe_fetch_message(chan, game.message_xid, game.guild_xid)
        if not post:
            return

        wait = await self.average_wait(session, game)
        await post.edit(embed=game.to_embed(wait=wait))

    async def safe_send_not_verified(
        self,
        author: discord.User,
        channel_settings: ChannelSettings,
        channel_name: str,
    ) -> None:
        not_verified_message = s(
            "not_verified",
            reply=author.mention,
            channel=channel_name,
        )
        if channel_settings.verify_message:
            not_verified_message = channel_settings.verify_message
        await safe_send_user(author, not_verified_message)

    async def process(self, message: discord.Message, prefix: str) -> None:
        """Process a command message."""
        tokens = message.content.split(" ")
        request, params = tokens[0][len(prefix) :].lower(), tokens[1:]
        params = list(filter(None, params))  # ignore any empty string parameters
        if not request:
            return

        # Special handling for `!powerX`: Tease apart the command request from parameter.
        if request.startswith("power") and len(request) > 5 and request[5:].isdigit():
            params.insert(0, request[5:])
            request = "power"

        # Ignore !help because so many other bots use it, use `!spellbot help` instead.
        if request.startswith("help"):
            return

        matching = [command for command in self.commands if command.startswith(request)]
        if not matching:
            post = await safe_send_channel(
                message.channel,
                s(
                    "not_a_command",
                    reply=message.author.mention,
                    request=request,
                    prefix=prefix,
                ),
            )
            if post:
                self.loop.call_later(
                    CLEAN_S, asyncio.create_task, safe_delete_message(post)
                )
            return
        if len(matching) > 1 and request not in matching:
            possible = ", ".join(f"{prefix}{m}" for m in matching)
            post = await safe_send_channel(
                message.channel,
                s(
                    "did_you_mean",
                    reply=message.author.mention,
                    possible=possible,
                ),
            )
            if post:
                self.loop.call_later(
                    CLEAN_S, asyncio.create_task, safe_delete_message(post)
                )
            return

        command = request if request in matching else matching[0]
        method = getattr(self, command)
        if not method.allow_dm and str(message.channel.type) == "private":
            author_user = cast(discord.User, message.author)
            await safe_send_user(author_user, s("no_dm", reply=message.author.mention))
            return
        if method.admin_only and not await check_is_admin(message):
            return
        logger.debug("%s%s (params=%s, message=%s)", prefix, command, params, message)
        if command in ["block", "unblock"]:
            # take one big parameter, including all spaces
            await method(prefix, [" ".join(tokens[1:])], message)
        else:
            await method(prefix, params, message)

    ##############################
    # Discord Client Behavior
    ##############################

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Behavior when the client gets a new reaction on a Discord message."""
        emoji = str(payload.emoji)
        if emoji not in [EMOJI_JOIN_GAME, EMOJI_DROP_GAME]:
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

        # NOTE: This and the code that handles !lfg commands is behind an async
        #       channel lock to prevent more than one person per guild per channel
        #       concurrently interleaving processing within this critical section.
        async with self.session() as session, self.channel_lock(payload.channel_id):
            assert payload.guild_id is not None
            server = self.ensure_server_exists(session, payload.guild_id)
            user = self.ensure_user_exists(session, author)

            if user.banned:
                await safe_remove_reaction(message, emoji, author)
                return

            if not server.bot_allowed_in(channel.id):
                return

            channel_settings = self.ensure_channel_settings_exists(
                session, server, payload.channel_id, message.channel.name
            )
            if channel_settings.require_verification:
                user_settings = self.ensure_user_settings_exists(session, user, server)
                if not user_settings.verified:
                    await self.safe_send_not_verified(
                        author, channel_settings, message.channel.name
                    )
                    await safe_remove_reaction(message, emoji, author)
                    return

            game = (
                session.query(Game).filter(Game.message_xid == message.id).one_or_none()
            )
            if not game or game.status != "pending":
                return  # this isn't a post relating to a pending game, just ignore it

            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=server.expire)

            await safe_remove_reaction(message, emoji, author)

            session.add(
                Metric(
                    kind="user_reaction",
                    guild_xid=payload.guild_id,
                    channel_xid=payload.channel_id,
                    user_xid=author.id,
                )
            )

            if emoji == EMOJI_JOIN_GAME:
                if any(user.xid == game_user.xid for game_user in game.users):
                    # this author is already in this game, they don't need to be added
                    return
                if user.blocked(game):
                    return
                if (
                    user.game
                    and user.game.id != game.id
                    and user.game.status != "started"
                ):
                    # this author is already another game, leave that one now
                    game_to_update = user.game
                    user.game_id = None  # type: ignore
                    session.commit()
                    await self.try_to_update_game(session, game_to_update)
                user.game = game
            else:  # emoji == EMOJI_DROP_GAME:
                if not any(user.xid == game_user.xid for game_user in game.users):
                    # this author is not in this game, so they can't be removed from it
                    return

                # update the game and remove the user from the game
                game.updated_at = now
                game.expires_at = expires_at
                user.game_id = None  # type: ignore
                session.commit()

                # update the game message
                wait = await self.average_wait(session, game)
                await safe_edit_message(message, embed=game.to_embed(wait=wait))
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
                game.url = (
                    self.create_spelltable_url() if game.system == "spelltable" else None
                )
                await self.setup_voice(session, game)
                game.status = "started"
                game.game_power = game.power  # type: ignore
                session.commit()
                for game_user in game.users:
                    session.add(Play(user_xid=game_user.xid, game_id=game.id))
                    user_award = self.ensure_user_award_exists(
                        session, game_user.xid, game.guild_xid
                    )
                    plays = user_award.plays or 0
                    user_award.plays = plays + 1  # type: ignore
                session.commit()
                for discord_user in found_discord_users:
                    await safe_send_user(discord_user, embed=game.to_embed(dm=True))
                await safe_edit_message(message, embed=game.to_embed())
                await safe_clear_reactions(message)
                await self.send_watch_list_notifications(session, game)
            else:
                session.commit()
                wait = await self.average_wait(session, game)
                await safe_edit_message(message, embed=game.to_embed(wait=wait))

    async def on_message(self, message: discord.Message) -> None:
        """Behavior when the client gets a message from Discord."""
        try:
            private = str(message.channel.type) == "private"

            # only respond in text channels and to direct messages
            if not private and str(message.channel.type) != "text":
                return

            if not private:
                rows = self.data.conn.execute(
                    text(
                        """
                        SELECT prefix
                        FROM servers
                        WHERE guild_xid = :g
                    """
                    ),
                    g=message.channel.guild.id,
                )
                values = [(row.prefix,) for row in rows]
                prefix = values[0][0] if values and values[0] else "!"
            else:
                prefix = "!"

            # auto-verify this user if this channel does auto-verification
            if not private:
                rows = self.data.conn.execute(
                    text(
                        """
                        SELECT
                            CASE channel_xid
                            WHEN :c THEN
                                1
                            ELSE
                                0
                            END
                        FROM
                            auto_verify_channels
                        WHERE
                            guild_xid = :g
                    """
                    ),
                    g=message.channel.guild.id,
                    c=message.channel.id,
                )
                items = [row for row in rows]
                does_auto_verify = (len(items) == 0) or (any(item[0] for item in items))
                if does_auto_verify:
                    async with self.session() as session:
                        server = self.ensure_server_exists(
                            session, message.channel.guild.id
                        )
                        user = self.ensure_user_exists(session, message.author)
                        user_settings = self.ensure_user_settings_exists(
                            session, user, server
                        )
                        if not user_settings.verified:
                            user_settings.verified = True  # type: ignore
                            session.commit()

            has_admin_perms: bool = False
            is_owner: bool = False
            is_mod: bool = False
            is_mentor: bool = False

            if not private and message.channel and message.channel.guild:
                guild = message.channel.guild
                if hasattr(guild, "get_member"):
                    member = guild.get_member(message.author.id)  # type: ignore
                    if member:
                        is_owner = member.id == guild.owner_id
                        if hasattr(member, "roles"):
                            is_mod = any(r.name == "Moderators" for r in member.roles)
                            is_mentor = any(r.name == "Mentors" for r in member.roles)
                        if hasattr(member, "permissions_in"):
                            perms = member.permissions_in(message.channel)
                            if perms:
                                has_admin_perms = perms.administrator

            # delete message if user verified and this is an unverified only channel
            if (
                not private
                # and not has_admin_perms
                # and not is_owner
                and not is_mod
                and not is_mentor
            ):
                rows = self.data.conn.execute(
                    text(
                        """
                        SELECT
                            CASE channel_xid
                            WHEN :c THEN
                                1
                            ELSE
                                0
                            END
                        FROM
                            unverified_only_channels
                        WHERE
                            guild_xid = :g
                    """
                    ),
                    g=message.channel.guild.id,
                    c=message.channel.id,
                )
                items = [row for row in rows]
                is_unverified_only = any(item[0] for item in items)
                if is_unverified_only:
                    async with self.session() as session:
                        server = self.ensure_server_exists(
                            session, message.channel.guild.id
                        )
                        user = self.ensure_user_exists(session, message.author)
                        user_settings = self.ensure_user_settings_exists(
                            session, user, server
                        )

                        if user_settings.verified:
                            # # Check we don't prevent Moderators and Mentors
                            # # from being able to freely chat in this channel.
                            # discord_user = safe_fetch_user(self, author.id)
                            # discord_user.role

                            await safe_delete_message(message)
                            return

            # only respond to command-like messages
            if not message.content.startswith(prefix):
                return

            async with self.session() as session:
                user = self.ensure_user_exists(session, message.author)
                if user.banned:
                    return

                if not private:
                    server = self.ensure_server_exists(session, message.channel.guild.id)
                    server_name = str(message.channel.guild)[0:50]
                    if not server.cached_name or server.cached_name != server_name:
                        server.cached_name = server_name  # type: ignore
                        session.commit()
                    user_settings = self.ensure_user_settings_exists(
                        session, user, server
                    )

                    if (
                        not has_admin_perms
                        and not is_owner
                        and not is_admin(message.channel, message.author)
                    ):
                        if not server.bot_allowed_in(message.channel.id):
                            return
                        channel_settings = self.ensure_channel_settings_exists(
                            session, server, message.channel.id, message.channel.name
                        )
                        if channel_settings.require_verification:
                            if not user_settings.verified:
                                discord_user = cast(discord.User, message.author)
                                await self.safe_send_not_verified(
                                    discord_user, channel_settings, message.channel.name
                                )
                                await safe_react_error(message)
                                return

            await self.process(message, prefix)

        except Exception as e:
            logging.exception("unhandled exception: %s", e)
            raise

    async def on_ready(self) -> None:
        """Behavior when the client has successfully connected to Discord."""
        logger.debug("logged in as %s", self.user)
        begin_background_tasks(self)

    ##############################
    # Bot Command Functions
    ##############################

    # Any method of this class with a name that is decorated by @command is detected as a
    # bot command. These methods should have a signature like:
    #
    #     @command(allow_dm=True, admin_only=False, help_group="Hi")
    #     def command_name(self, prefix, params, message)
    #
    # - `allow_dm` indicates if the command is allowed to be used in direct messages.
    # - `admin_only` indicates if the command is available only to admins.
    # - `help_group` is the group name for this command in the usage help response.
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

    # @command(allow_dm=True, help_group="Commands for Players")
    async def help(
        self, prefix: str, params: List[str], message: discord.Message
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
            "💜 You can help keep SpellBot running by becoming a patron! "
            "<https://www.patreon.com/lexicalunit>"
        )
        if str(message.channel.type) != "private":
            await safe_react_ok(message)
        for page in paginate(usage):
            await safe_send_user(cast(discord.User, message.author), page)

    @command(allow_dm=True, help_group="Commands for Players")
    async def about(
        self, prefix: str, params: List[str], message: discord.Message
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
            f"Use the command `{prefix}spellbot help` for usage details. "
            "Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
            "\n"
            f"[🔗 Add SpellBot to your Discord!]({INVITE_LINK})\n"
            "\n"
            f"[👍 Give SpellBot a vote on top.gg!]({VOTE_LINK})\n"
            "\n"
            "💜 Help keep SpellBot running by "
            "[becoming a patron!](https://www.patreon.com/lexicalunit)"
        )
        embed.url = "http://spellbot.io/"
        embed.color = discord.Color(0x5A3EFD)
        await safe_send_channel(message.channel, embed=embed)
        await safe_react_ok(message)

    async def _validate_size(self, msg: discord.Message, size: Optional[int]) -> bool:
        if not size or not (1 < size < 5):
            await safe_send_channel(
                msg.channel, s("game_size_bad", reply=msg.author.mention)
            )
            return False
        return True

    async def _validate_mentions_size(
        self, msg: discord.Message, mentions: List[Any], size: int
    ) -> bool:
        if len(mentions) >= size:
            await safe_send_channel(
                msg.channel, s("lfg_too_many_mentions", reply=msg.author.mention)
            )
            return False
        return True

    async def _validate_tags_size(self, msg: discord.Message, tags: List[str]) -> bool:
        if len(tags) > 5:
            await safe_send_channel(
                msg.channel, s("tags_too_many", reply=msg.author.mention)
            )
            return False
        return True

    async def _remove_user_from_game(self, session: Session, user: User):
        """If the user is currently in a game, take them out of it."""
        if user.waiting:
            game_to_update = user.game
            user.game_id = None  # type: ignore
            session.commit()
            await self.try_to_update_game(session, game_to_update)

    async def _respond_found_game(
        self, msg: discord.Message, user: discord.User, game: Game
    ) -> Optional[discord.Message]:
        # TODO: games will always have a message_xid even tho it's nullable in the db...
        assert game.message_xid
        post = await safe_fetch_message(msg.channel, game.message_xid, game.guild_xid)
        if not post:
            return None
        link = post_link(game.server.guild_xid, msg.channel.id, game.message_xid)
        embed = discord.Embed()
        embed.set_thumbnail(url=ICO_URL)
        embed.set_author(name=s("play_found_title"))
        embed.description = s("play_found_desc", reply=user.mention, link=link)
        embed.color = discord.Color(0x5A3EFD)
        await safe_send_channel(msg.channel, embed=embed)
        return post

    async def _add_user_to_game(self, session: Session, user: User, game: Game) -> None:
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=game.server.expire)
        user.game = game
        user.game.expires_at = expires_at  # type: ignore
        user.game.updated_at = now  # type: ignore
        session.commit()

    async def _post_new_game(
        self, session: Session, msg: discord.Message, game: Game
    ) -> Optional[discord.Message]:
        wait = await self.average_wait(session, game)
        post = await safe_send_channel(msg.channel, embed=game.to_embed(wait=wait))
        if not post:
            return None

        game.message_xid = post.id  # type: ignore
        session.commit()
        await safe_react_emoji(post, EMOJI_JOIN_GAME)
        await safe_react_emoji(post, EMOJI_DROP_GAME)
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
                game_url = (
                    self.create_spelltable_url() if game.system == "spelltable" else None
                )
                game.url = game_url  # type: ignore
                await self.setup_voice(session, game)
                game.status = "started"  # type: ignore
                game.game_power = game.power  # type: ignore
                session.commit()
                for game_user in game.users:
                    session.add(Play(user_xid=game_user.xid, game_id=game.id))
                    user_award = self.ensure_user_award_exists(
                        session, game_user.xid, game.guild_xid
                    )
                    plays = user_award.plays or 0
                    user_award.plays = plays + 1  # type: ignore
                session.commit()
                for discord_user in found_discord_users:
                    await safe_send_user(discord_user, embed=game.to_embed(dm=True))
                await safe_edit_message(post, embed=game.to_embed())
                await safe_clear_reactions(post)
                await self.send_watch_list_notifications(session, game)
                return
        else:  # game *definitely* isn't ready yet
            wait = await self.average_wait(session, game)
            await safe_edit_message(post, embed=game.to_embed(wait=wait))

    async def _call_attention_to_game(self, msg: discord.Message, game: Game) -> bool:
        if not game.message_xid:
            return False

        post = await safe_fetch_message(msg.channel, game.message_xid, game.guild_xid)
        if not post:
            return False

        link = post_link(game.server.guild_xid, msg.channel.id, game.message_xid)
        embed = discord.Embed()
        embed.set_thumbnail(url=ICO_URL)
        remaining = int(game.size) - len(cast(List[User], game.users))
        plural = "s" if remaining > 1 else ""
        embed.set_author(name=s("call_attn_title", remaining=remaining, plural=plural))
        embed.description = s("call_attn_desc", link=link)
        embed.color = discord.Color(0x5A3EFD)
        await safe_send_channel(msg.channel, embed=embed)
        return True

    async def _play_helper(
        self,
        session: Session,
        prefix: str,
        params: List[str],
        message: discord.Message,
    ) -> None:
        server = self.ensure_server_exists(session, message.channel.guild.id)
        channel_settings = self.ensure_channel_settings_exists(
            session, server, message.channel.id, message.channel.name
        )
        user = self.ensure_user_exists(session, message.author)
        mentions = message.mentions if message.channel.type != "private" else []

        if user.waiting and user.game.channel_xid == message.channel.id:
            await self._call_attention_to_game(message, user.game)
            await safe_react_ok(message)
            return

        opts = parse_opts(params, default_size=channel_settings.default_size)
        size: Optional[int] = opts["size"]
        tag_names: List[str] = opts["tags"]
        system: str = opts["system"]
        note = " ".join(p for p in opts["params"] if not p.startswith("<@"))

        tags_enabled = (
            channel_settings.tags_enabled
            if channel_settings.tags_enabled is not None
            else server.tags_enabled
        )
        if not tags_enabled:
            tag_names = []

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

        # you can only add mentioned users to the game if they're not waiting
        free_users = [u for u in mentioned_users if not u.waiting]

        new_game = False
        game = Game.find_existing(
            session=session,
            server=server,
            channel_xid=message.channel.id,
            size=size,
            seats=1 + len(free_users),
            tags=tags,
            system=system,
            power=user.power,
        )

        # check if anyone in this game has the other blocked,
        # if so don't put this user into this existing game
        if game and user.blocked(game):
            game = None

        if not game:
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
                note=note,
            )

        await self._remove_user_from_game(session, user)
        await self._add_user_to_game(session, user, game)
        for free_user in free_users:
            await self._add_user_to_game(session, free_user, game)

        post: Optional[discord.Message] = None
        if new_game:
            post = await self._post_new_game(session, message, game)
        else:
            discord_user = cast(discord.User, message.author)
            post = await self._respond_found_game(message, discord_user, game)
            if not post:  # the post must have been deleted
                post = await self._post_new_game(session, message, game)

        if post:
            await self._update_or_start_game(session, game, post)
            await safe_react_ok(message)

    @command(allow_dm=False, help_group="Commands for Players")
    async def lfg(self, prefix: str, params: List[str], message: discord.Message) -> None:
        """
        Find or create a pending game for players to join.

        The default game size is 4 but you can change it by adding, for example, `size:2`
        to create a two player game.

        You can automatically join players already in a game by @ mentioning them in the
        command.

        Players will be able to enter or leave the game by reacting to the message that
        SpellBot sends.

        Up to five tags can be given as well to help describe the game experience that you
        want. For example you might send `!lfg ~no-combo ~proxy` which will assign the
        tags `no-combo` and `proxy` to your game. People will be able to see what tags
        are set on your game when they are looking for games to join.
        & [size:N] [@player-1] [@player-2] ... [~tag-1] [~tag-2] ...
        """
        # NOTE: This and the code to handle message reactions is behind an async
        #       channel lock to prevent more than one person per guild per channel
        #       concurrently interleaving processing within this critical section.
        async with self.channel_lock(message.channel.id):
            async with self.session() as session:
                await self._play_helper(session, prefix, params, message)

    def _upsert_user_block(self, session: Session, user: User, blocked: User) -> None:
        data = {"user_xid": user.xid, "blocked_user_xid": blocked.xid}
        if "postgres" in session.bind.dialect.name:
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(users_blocks).values(data)
            session.execute(stmt.on_conflict_do_nothing(constraint="uix_1"))
        else:
            # The type: ignore used here is a workaround to a mypy issue,
            # more details here: https://github.com/python/mypy/issues/1153
            from sqlalchemy import insert  # type: ignore

            filters = [
                users_blocks.c.user_xid == user.xid,
                users_blocks.c.blocked_user_xid == blocked.xid,
            ]
            query = session.query(users_blocks).filter(and_(*filters))
            exists = session.query(query.exists()).scalar()
            if not exists:
                session.execute(insert(users_blocks).values(data))

    @command(allow_dm=False, help_group="Commands for Players")
    async def block(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Block a user, by name, from joining your games. Do NOT use a mention.
        & <user name>
        """
        author = message.author
        author_user = cast(discord.User, author)
        reply = author.mention
        guild_xid = message.channel.guild.id
        mentions = message.mentions
        finder = create_member_finder(message)

        await safe_delete_message(message)  # delete ASAP to avoid drama

        if len(mentions) != 0:
            await safe_send_user(author_user, s("block_mentions", reply=reply))
            return

        if len(params) == 0 or not params[0]:
            await safe_send_user(author_user, s("block_no_params", reply=reply))
            return

        block_name = params[0]
        found_user: Optional[discord.User] = None

        async with self.session() as session:
            server = self.ensure_server_exists(session, guild_xid)
            user = self.ensure_user_exists(session, author)
            self.ensure_user_settings_exists(session, user, server)
            mentioned = finder.find(block_name)
            if mentioned and mentioned.id == author_user.id:
                await safe_send_user(author_user, s("block_no_params", reply=reply))
                return
            if mentioned:
                found_user = mentioned
                blocked_user = self.ensure_user_exists(session, mentioned)
                self.ensure_user_settings_exists(session, blocked_user, server)
                self._upsert_user_block(session, user, blocked_user)
            session.commit()

        if not found_user:
            await safe_send_user(
                author_user, s("block_not_found", reply=reply, name=block_name)
            )
            return

        mention_str = f"@{found_user.name}"
        await safe_send_user(author_user, s("block", reply=reply, blocked=mention_str))

    @command(allow_dm=False, help_group="Commands for Players")
    async def unblock(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Unblock a previously blocked user by name. Do NOT use a mention.
        & <user name>
        """
        author = message.author
        author_user = cast(discord.User, author)
        reply = author.mention
        guild_xid = message.channel.guild.id
        mentions = message.mentions
        finder = create_member_finder(message)

        await safe_delete_message(message)  # delete ASAP to avoid drama

        if len(mentions) != 0:
            await safe_send_user(author_user, s("unblock_mentions", reply=reply))
            return

        if len(params) == 0 or not params[0]:
            await safe_send_user(author_user, s("unblock_no_params", reply=reply))
            return

        unblock_name = params[0]
        found_user: Optional[discord.User] = None

        async with self.session() as session:
            server = self.ensure_server_exists(session, guild_xid)
            user = self.ensure_user_exists(session, author)
            self.ensure_user_settings_exists(session, user, server)
            mentioned = finder.find(unblock_name)
            if mentioned:
                found_user = mentioned
                blocked_user = self.ensure_user_exists(session, mentioned)
                self.ensure_user_settings_exists(session, blocked_user, server)
                filters = [
                    users_blocks.c.user_xid == user.xid,
                    users_blocks.c.blocked_user_xid == blocked_user.xid,
                ]
                session.query(users_blocks).filter(and_(*filters)).delete(
                    synchronize_session=False
                )
            session.commit()

        if not found_user:
            await safe_send_user(
                author_user, s("unblock_not_found", reply=reply, name=unblock_name)
            )
            return

        mention_s = f"@{found_user.name}"
        await safe_send_user(author_user, s("unblock", reply=reply, unblocked=mention_s))

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
            await safe_send_channel(
                message.channel,
                s(
                    "report_wrong",
                    reply=message.author.mention,
                    prefix=prefix,
                ),
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
            await safe_send_channel(
                message.channel,
                s(
                    "report_wrong",
                    reply=message.author.mention,
                    prefix=prefix,
                ),
            )
            return False

        return True

    @command(allow_dm=False, help_group="Commands for Players")
    async def report(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Report your results on a finished game.
        & <Game ID> ...
        """
        if len(params) < 2:
            await safe_send_channel(
                message.channel, s("report_no_params", reply=message.author.mention)
            )
            await safe_react_error(message)
            return

        req = params[0]
        report_str = " ".join(params[1:])

        if len(report_str) >= 255:
            await safe_send_channel(
                message.channel, s("report_too_long", reply=message.author.mention)
            )
            await safe_react_error(message)
            return

        async with self.session() as session:
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
                await safe_send_channel(
                    message.channel,
                    s(
                        "report_no_game",
                        reply=message.author.mention,
                    ),
                )
                await safe_react_error(message)
                return

            if not game.status == "started":
                await safe_send_channel(
                    message.channel,
                    s(
                        "report_not_started",
                        reply=message.author.mention,
                    ),
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
            await safe_send_channel(
                message.channel, s("report", reply=message.author.mention)
            )
            await safe_react_ok(message)

    @command(allow_dm=False, admin_only=False, help_group="Commands for Players")
    async def points(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Get your total points on this server.
        """
        async with self.session() as session:
            user = self.ensure_user_exists(session, message.author)
            server = self.ensure_server_exists(session, message.channel.guild.id)
            points = user.points(server.guild_xid)

            await safe_send_channel(
                message.channel,
                s(
                    "points",
                    reply=message.author.mention,
                    points=points,
                ),
            )

            if is_admin(message.channel, message.author):
                team_points = Team.points(session, message.channel.guild.id)
                for team, team_points in team_points.items():
                    await safe_send_channel(
                        message.channel,
                        s(
                            "points_team",
                            reply=message.author.mention,
                            team=team,
                            points=team_points,
                        ),
                    )

            await safe_react_ok(message)

    def decode_data(self, bdata):
        return bdata.decode("utf-8")

    @command(allow_dm=False, admin_only=True, help_group="Commands for Admins")
    async def event(
        self, prefix: str, params: List[str], message: discord.Message
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
            await safe_send_channel(
                message.channel, s("event_no_data", reply=message.author.mention)
            )
            await safe_react_error(message)
            return
        if not params:
            await safe_send_channel(
                message.channel, s("event_no_params", reply=message.author.mention)
            )
            await safe_react_error(message)
            return

        async with self.session() as session:
            server = self.ensure_server_exists(session, message.channel.guild.id)
            channel_settings = self.ensure_channel_settings_exists(
                session, server, message.channel.id, message.channel.name
            )

            opts = parse_opts(params, default_size=channel_settings.default_size)
            params, tag_names, opt_msg, system = (
                opts["params"],
                opts["tags"],
                opts["message"],
                opts["system"],
            )
            size = len(params)
            attachment = message.attachments[0]

            if len(tag_names) > 5:
                await safe_send_channel(
                    message.channel, s("tags_too_many", reply=message.author.mention)
                )
                await safe_react_error(message)
                return
            if opt_msg and len(opt_msg) >= 255:
                await safe_send_channel(
                    message.channel,
                    s(
                        "game_message_too_long",
                        reply=message.author.mention,
                    ),
                )
                await safe_react_error(message)
                return
            if not (1 < size <= 4):
                await safe_send_channel(
                    message.channel,
                    s(
                        "event_bad_play_count",
                        reply=message.author.mention,
                    ),
                )
                await safe_react_error(message)
                return
            if not attachment.filename.lower().endswith(".csv"):
                await safe_send_channel(
                    message.channel, s("event_not_csv", reply=message.author.mention)
                )
                await safe_react_error(message)
                return

            tags = Tag.create_many(session, tag_names)

            bdata = await message.attachments[0].read()
            try:
                sdata = self.decode_data(bdata)
            except UnicodeDecodeError:
                await safe_send_channel(
                    message.channel,
                    s(
                        "event_not_utf",
                        reply=message.author.mention,
                    ),
                )
                await safe_react_error(message)
                return

            reader = csv.reader(StringIO(sdata))
            header = [column.lower().strip() for column in next(reader)]
            params = [param.lower().strip() for param in params]

            if any(param not in header for param in params):
                await safe_send_channel(
                    message.channel,
                    s(
                        "event_no_header",
                        reply=message.author.mention,
                    ),
                )
                await safe_react_error(message)
                return

            columns = [header.index(param) for param in params]

            event = Event()
            session.add(event)
            session.commit()

            players_in_this_event: Set[str] = set()
            warnings = set()

            finder = create_member_finder(message)

            for i, row in enumerate(reader):
                csv_row_data = [row[column].strip() for column in columns]
                players_s = ", ".join([f'"{value}"' for value in csv_row_data])
                player_names = [
                    re.sub("#.*$", "", value.lower()).lstrip("@")
                    for value in csv_row_data
                ]

                for player_name in player_names:
                    if not finder.find(player_name):
                        warning = s("event_missing_player", row=i + 1, players=players_s)
                        await safe_send_channel(message.channel, warning)
                        continue

                player_discord_users: List[discord.User] = []
                for csv_data, player_name in zip(csv_row_data, player_names):
                    if player_name in players_in_this_event:
                        await safe_send_channel(
                            message.channel,
                            s(
                                "event_duplicate_user",
                                row=i + 1,
                                name=csv_data,
                                players=players_s,
                            ),
                        )
                        await safe_react_error(message)
                        return
                    player_discord_user = finder.find(player_name)
                    if player_discord_user:
                        players_in_this_event.add(player_name)
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
                        player_user.game_id = None  # type: ignore
                        await self.try_to_update_game(session, game_to_update)
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
                    await safe_send_channel(message.channel, page)

            if not event.games:
                session.delete(event)
                await safe_send_channel(
                    message.channel, s("event_empty", reply=message.author.mention)
                )
                await safe_react_error(message)
                return

            session.commit()
            count = len([game for game in event.games])
            await safe_send_channel(
                message.channel,
                s(
                    "event_created",
                    reply=message.author.mention,
                    prefix=prefix,
                    event_id=event.id,
                    count=count,
                ),
            )
            await safe_react_ok(message)

    @command(allow_dm=False, admin_only=True, help_group="Commands for Admins")
    async def begin(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Confirm creation of games for the given event id. _Requires the
        "SpellBot Admin" role._
        & <event id>
        """
        if not params:
            await safe_send_channel(
                message.channel, s("begin_no_params", reply=message.author.mention)
            )
            await safe_react_error(message)
            return

        event_id = to_int(params[0])
        if not event_id:
            await safe_send_channel(
                message.channel, s("begin_bad_event", reply=message.author.mention)
            )
            await safe_react_error(message)
            return

        async with self.session() as session:
            event: Optional[Event] = (
                session.query(Event).filter(Event.id == event_id).one_or_none()
            )
            if not event:
                await safe_send_channel(
                    message.channel,
                    s(
                        "begin_bad_event",
                        reply=message.author.mention,
                    ),
                )
                await safe_react_error(message)
                return

            if event.started:
                await safe_send_channel(
                    message.channel,
                    s(
                        "begin_event_already_started",
                        reply=message.author.mention,
                    ),
                )
                await safe_react_error(message)
                return

            for game in cast(List[Game], event.games):
                # Can't rely on "<@{xid}>" working because the user could have logged out.
                # But if we don't have the cached name, we just have to fallback to it.
                # Support <@!USERID> for server nick?
                sorted_names = sorted(
                    [user.cached_name or f"<@{user.xid}>" for user in game.users]
                )
                players_str = ", ".join(cast(List[str], sorted_names))

                found_discord_users = []
                for game_user in game.users:
                    discord_user = await safe_fetch_user(self, game_user.xid)
                    if (
                        not discord_user
                    ):  # game_user has left the server since event created
                        warning = s("begin_user_left", players=players_str)
                        await safe_send_channel(message.channel, warning)
                    else:
                        found_discord_users.append(discord_user)
                if len(found_discord_users) != len(cast(List[User], game.users)):
                    continue

                game_url = (
                    self.create_spelltable_url() if game.system == "spelltable" else None
                )
                game.url = game_url  # type: ignore
                await self.setup_voice(session, game)
                game.status = "started"  # type: ignore
                game.game_power = game.power  # type: ignore
                response = game.to_embed(dm=True)
                session.commit()
                for game_user in game.users:
                    session.add(Play(user_xid=game_user.xid, game_id=game.id))
                session.commit()

                for discord_user in found_discord_users:
                    await safe_send_user(discord_user, embed=response)

                await safe_send_channel(
                    message.channel,
                    s(
                        "game_created",
                        reply=message.author.mention,
                        id=game.id,
                        url=game.url,
                        players=players_str,
                    ),
                )
                await safe_react_ok(message)
                await self.send_watch_list_notifications(session, game)

    @command(allow_dm=False, admin_only=True, help_group="Commands for Admins")
    async def game(
        self, prefix: str, params: List[str], message: discord.Message
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
        async with self.session() as session:
            server = self.ensure_server_exists(session, message.channel.guild.id)
            channel_settings = self.ensure_channel_settings_exists(
                session, server, message.channel.id, message.channel.name
            )

            opts = parse_opts(params, default_size=channel_settings.default_size)
            size, tag_names, opt_msg, system = (
                opts["size"],
                opts["tags"],
                opts["message"],
                opts["system"],
            )
            mentions = message.mentions if message.channel.type != "private" else []

            if opt_msg and len(opt_msg) >= 255:
                await safe_send_channel(
                    message.channel,
                    s(
                        "game_message_too_long",
                        reply=message.author.mention,
                    ),
                )
                await safe_react_error(message)
                return
            if tag_names and len(tag_names) > 5:
                await safe_send_channel(
                    message.channel, s("tags_too_many", reply=message.author.mention)
                )
                await safe_react_error(message)
                return

            if not size or not (1 < size <= 4):
                await safe_send_channel(
                    message.channel, s("game_size_bad", reply=message.author.mention)
                )
                await safe_react_error(message)
                return

            if len(mentions) > size:
                await safe_send_channel(
                    message.channel,
                    s(
                        "game_too_many_mentions",
                        reply=message.author.mention,
                        size=size,
                    ),
                )
                await safe_react_error(message)
                return

            if len(mentions) < size:
                await safe_send_channel(
                    message.channel,
                    s(
                        "game_too_few_mentions",
                        reply=message.author.mention,
                        size=size,
                    ),
                )
                await safe_react_error(message)
                return

            mentioned_users = []
            for mentioned in mentions:
                mentioned_user = self.ensure_user_exists(session, mentioned)
                if mentioned_user.waiting:
                    game_to_update = mentioned_user.game
                    mentioned_user.game_id = None  # type: ignore
                    await self.try_to_update_game(session, game_to_update)
                mentioned_users.append(mentioned_user)
            session.commit()

            tags = Tag.create_many(session, tag_names)

            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=server.expire)
            url = self.create_spelltable_url() if system == "spelltable" else None
            game = Game(
                channel_xid=message.channel.id,
                created_at=now,
                expires_at=expires_at,
                server=server,
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
            for game_user in game.users:
                session.add(Play(user_xid=game_user.xid, game_id=game.id))

            if server.create_voice:
                category_prefix = server.voice_category_prefix or VOICE_CATEGORY_PREFIX
                await self.setup_voice(session, game, prefix=category_prefix)
                session.commit()

            player_response = game.to_embed(dm=True)
            for player in mentioned_users:
                discord_user = await safe_fetch_user(self, player.xid)
                # TODO: What happens if discord_user is None?
                if discord_user:
                    await safe_send_user(discord_user, embed=player_response)

            players_str = ", ".join(
                # Support <@!USERID> for server nick?
                sorted([f"<@{user.xid}>" for user in mentioned_users])
            )
            resp_args = {
                "reply": message.author.mention,
                "id": game.id,
                "url": game.url,
                "voice": game.voice_channel_invite,
                "players": players_str,
            }
            if server.create_voice:
                await safe_send_channel(
                    message.channel, s("game_created_with_voice", **resp_args)
                )
            else:
                del resp_args["voice"]
                await safe_send_channel(message.channel, s("game_created", **resp_args))
            await safe_react_ok(message)

    @command(allow_dm=True, help_group="Commands for Players")
    async def leave(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Leave any pending games that you've signed up.
        """
        async with self.session() as session:
            user = self.ensure_user_exists(session, message.author)
            if user.waiting:
                game = user.game
                user.game_id = None  # type: ignore
                session.commit()
                await self.try_to_update_game(session, game)
            await safe_react_ok(message)

    @command(allow_dm=False, admin_only=True, help_group="Commands for Admins")
    async def export(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Exports historical game data to a CSV file. _Requires the "SpellBot Admin" role._
        """
        async with self.session() as session:
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
                            name = cast(discord.TextChannel, channel).name
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
            await safe_send_channel(message.channel, "", file=discord.File(export_file))
            await safe_react_ok(message)

    @command(allow_dm=True, help_group="Commands for Players")
    async def power(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Set or unset the power level of the deck you are going to play.
        **You DO NOT NEED to have a power level set to use SpellBot.**

        When you have set a power level, the !lfg and !find commands will try to put
        you in games with other players of similar power levels.
        & <none | 1..10>
        """
        async with self.session() as session:
            if str(message.channel.type) != "private":
                server = self.ensure_server_exists(session, message.channel.guild.id)
                if not server.power_enabled:
                    return

            async def send_invalid(prepend) -> None:
                await safe_send_channel(
                    message.channel,
                    s(
                        "power_invalid",
                        reply=message.author.mention,
                        prepend=prepend,
                    ),
                )
                await safe_react_error(message)

            if not params:
                return await send_invalid("")

            user = self.ensure_user_exists(session, message.author)

            power = params[0].lower()
            if power in ["none", "off", "unset", "no", "0"]:
                user.power = None  # type: ignore
                session.commit()
                await safe_react_ok(message)
                if user.waiting:
                    await self.try_to_update_game(session, user.game)
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

            user.power = power_i  # type: ignore
            session.commit()
            await safe_react_ok(message)
            if user.waiting:
                await self.try_to_update_game(session, user.game)
            await safe_react_ok(message)

    @command(allow_dm=False, help_group="Commands for Players")
    async def team(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Set or get your team on this server. To get your team name, run this command with
        no parameters.
        & [team-name]
        """
        async with self.session() as session:
            server = self.ensure_server_exists(session, message.channel.guild.id)
            if not server.teams:
                await safe_send_channel(
                    message.channel, s("team_none", reply=message.author.mention)
                )
                await safe_react_error(message)
                return

            user = self.ensure_user_exists(session, message.author)
            if not params:
                user_settings = self.ensure_user_settings_exists(session, user, server)
                if user_settings.team_id is None:
                    await safe_send_channel(
                        message.channel,
                        s(
                            "team_not_set",
                            reply=message.author.mention,
                        ),
                    )
                    await safe_react_error(message)
                    return

                team = (
                    session.query(Team).filter_by(id=user_settings.team_id).one_or_none()
                )
                if not team:
                    user_settings.team_id = None  # type: ignore
                    session.commit()
                    await safe_send_channel(
                        message.channel,
                        s(
                            "team_gone",
                            reply=message.author.mention,
                        ),
                    )
                    await safe_react_error(message)
                    return

                await safe_send_channel(
                    message.channel,
                    s(
                        "team_yours",
                        reply=message.author.mention,
                        team=team.name,
                    ),
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
                await safe_send_channel(
                    message.channel,
                    s(
                        "team_not_found",
                        reply=message.author.mention,
                        teams=teams,
                    ),
                )
                await safe_react_error(message)
                return

            user_settings = self.ensure_user_settings_exists(session, user, server)
            if user_settings.team_id != team_found.id:
                user_settings.team_id = team_found.id  # type: ignore
            session.commit()
            await safe_react_ok(message)

    async def _set_verified(
        self, prefix: str, params: List[str], message: discord.Message, setting: bool
    ) -> None:
        if not await check_is_admin(message):
            await safe_react_error(message)
            return

        if len(message.mentions) == 0:
            await safe_react_error(message)
            return
        async with self.session() as session:
            server = self.ensure_server_exists(session, message.channel.guild.id)
            for mentioned in message.mentions:
                user = self.ensure_user_exists(session, mentioned)
                user_settings = self.ensure_user_settings_exists(session, user, server)
                user_settings.verified = setting  # type: ignore
            session.commit()
        await safe_react_ok(message)

    @command(allow_dm=False, help_group="Commands for Admins")
    async def verify(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """Verify a user on your server."""
        await self._set_verified(prefix, params, message, True)

    @command(allow_dm=False, help_group="Commands for Admins")
    async def unverify(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """Unverify a user on your server."""
        await self._set_verified(prefix, params, message, False)

    async def _set_watched(
        self, prefix: str, params: List[str], message: discord.Message, setting: bool
    ) -> None:
        if not await check_is_admin(message):
            await safe_react_error(message)
            return

        if len(message.mentions) == 0:
            await safe_react_error(message)
            return

        note = " ".join(
            p for p in params if not p.startswith("<@") and not p.startswith("@")
        )
        if len(note) >= 255:
            await safe_send_channel(
                message.channel,
                s(
                    "watched_user_note_too_long",
                    reply=message.author.mention,
                    command=command,
                ),
            )
            await safe_react_error(message)
            return

        async with self.session() as session:
            server = self.ensure_server_exists(session, message.channel.guild.id)
            for mentioned in message.mentions:
                user = self.ensure_user_exists(session, mentioned)
                watched_user_q = session.query(WatchedUser).filter_by(
                    user_xid=user.xid, guild_xid=server.guild_xid
                )
                watched_user = watched_user_q.first()
                if watched_user and not setting:
                    watched_user_q.delete()
                if watched_user and setting:
                    watched_user.note = note  # type: ignore
                if not watched_user and setting:
                    watched_user = WatchedUser(
                        user_xid=user.xid, guild_xid=server.guild_xid, note=note
                    )
                    session.add(watched_user)
            session.commit()
        await safe_react_ok(message)

    @command(allow_dm=False, help_group="Commands for Admins")
    async def watch(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """Watch a user on your server."""
        await self._set_watched(prefix, params, message, True)

    @command(allow_dm=False, help_group="Commands for Admins")
    async def unwatch(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """Unwatch a user on your server."""
        await self._set_watched(prefix, params, message, False)

    @command(allow_dm=False, help_group="Commands for Admins")
    async def spellbot(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        """
        Configure SpellBot for your server. _Requires the "SpellBot Admin" role._

        The following subcommands are supported:
        * `config`: Just show the current configuration for this server.
        * `channels <list>`: Set SpellBot to only respond in the given list of channels.
        * `prefix <string>`: Set SpellBot's command prefix for text channels.
        * `links <private|public>`: Set the privacy for generated SpellTable links.
        * `spectate <on|off>`: Add a spectator link to the posts SpellBot makes.
        * `expire <number>`: Set the number of minutes before pending games expire.
        * `teams <list|none>`: Sets the teams available on this server.
        * `power <on|off>`: Turns the power command on or off for this server.
        * `voice <on|off>`: When on, SpellBot will automatically create voice channels.
        * `tags [channels] <on|off>`: Turn on or off the ability to use tags.
        * `queue-time [channels] <on|off>`: Turn on or off average queue time details.
        * `smotd <your message>`: Set the server message of the day.
        * `cmotd <your message>`: Set the message of the day for a channel.
        * `motd <private|public|both>`: Set the visibility of MOTD in game posts.
        * `size <integer>`: Sets the default game size for a specific channel.
        * `toggle-verify`: Toggles user verification on/off for a specific channel.
        * `auto-verify <list|all>`: Set the channels that trigger user auto verification.
        * `unverified-only <list>`: Set the channels that are only for unverified users.
        * `verify-message <your message>`: Set the verification message for this channel.
        * `voice-category <string>`: Set category for voice channels created by !game.
        * `awards`: Attach a config file to award users who have played enough games.
        * `stats`: Gets some statistics about SpellBot usage on your server.
        * `help`: Get detailed usage help for SpellBot.
        & <subcommand> [subcommand parameters]
        """
        if not params:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_missing_subcommand",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        command = params[0]
        if command == "help":
            await self.spellbot_help(prefix, params[1:], message)
            return

        if not await check_is_admin(message):
            await safe_react_error(message)
            return

        async with self.session() as session:
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
            elif command == "spectate":
                await self.spellbot_spectate(session, server, params[1:], message)
            elif command == "teams":
                await self.spellbot_teams(session, server, params[1:], message)
            elif command == "power":
                await self.spellbot_power(session, server, params[1:], message)
            elif command == "voice":
                await self.spellbot_voice(session, server, params[1:], message)
            elif command == "tags":
                await self.spellbot_tags(session, server, params[1:], message)
            elif command == "queue-time":
                await self.spellbot_queue_time(session, server, params[1:], message)
            elif command == "smotd":
                await self.spellbot_smotd(session, server, params[1:], message)
            elif command == "voice-category":
                await self.spellbot_voice_category(session, server, params[1:], message)
            elif command == "awards":
                await self.spellbot_awards(session, server, params[1:], message)
            elif command == "cmotd":
                await self.spellbot_cmotd(session, server, params[1:], message)
            elif command == "motd":
                await self.spellbot_motd(session, server, params[1:], message)
            elif command == "size":
                await self.spellbot_size(session, server, params[1:], message)
            elif command == "stats":
                await self.spellbot_stats(session, server, params[1:], message)
            elif command == "toggle-verify":
                await self.spellbot_toggle_verify(session, server, params[1:], message)
            elif command == "auto-verify":
                await self.spellbot_auto_verify(session, server, params[1:], message)
            elif command == "unverified-only":
                await self.spellbot_unverified_only(session, server, params[1:], message)
            elif command == "verify-message":
                await self.spellbot_verify_message(session, server, params[1:], message)
            else:
                await safe_send_channel(
                    message.channel,
                    s(
                        "spellbot_unknown_subcommand",
                        reply=message.author.mention,
                        command=command,
                    ),
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
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_channels_none",
                    reply=message.author.mention,
                ),
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
                await safe_send_channel(
                    message.channel,
                    s(
                        "spellbot_channels_warn",
                        reply=message.author.mention,
                        param=param,
                    ),
                )
                continue

            discord_channel = await safe_fetch_channel(self, int(m[1]), server.guild_xid)
            if not discord_channel:
                await safe_send_channel(
                    message.channel,
                    s(
                        "spellbot_channels_warn",
                        reply=message.author.mention,
                        param=param,
                    ),
                )
                continue

            channel = Channel(channel_xid=discord_channel.id, guild_xid=server.guild_xid)
            session.add(channel)
            channels.append(channel)
            session.commit()

        if all_channels:
            server.channels = []  # type: ignore
            session.commit()
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_channels",
                    reply=message.author.mention,
                    channels="all channels",
                ),
            )
        elif channels:
            server.channels = channels  # type: ignore
            session.commit()
            channels_str = ", ".join([f"<#{c.channel_xid}>" for c in channels])
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_channels",
                    reply=message.author.mention,
                    channels=channels_str,
                ),
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
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_prefix_none",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        prefix_str = params[0][0:10]
        server.prefix = prefix_str  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_prefix",
                reply=message.author.mention,
                prefix=prefix_str,
            ),
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
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_links_none",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        links_str = params[0].lower()
        if links_str not in ["private", "public"]:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_links_bad",
                    reply=message.author.mention,
                    input=params[0],
                ),
            )
            await safe_react_error(message)
            return

        server.links = links_str  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_links",
                reply=message.author.mention,
                setting=links_str,
            ),
        )
        await safe_react_ok(message)

    async def spellbot_spectate(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params or params[0].lower() not in ["on", "off"]:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_spectate_bad",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        setting = params[0].lower()
        server.show_spectate_link = setting == "on"  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_spectate",
                reply=message.author.mention,
                setting=setting,
            ),
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
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_expire_none",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        expire = to_int(params[0])
        if not expire or not (0 < expire <= 60):
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_expire_bad",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        server.expire = expire  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_expire",
                reply=message.author.mention,
                expire=expire,
            ),
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
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_teams_none",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        erase_all_teams = params[0].lower() == "none"

        if len(params) < 2 and not erase_all_teams:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_teams_too_few",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        # blow away any existing old teams
        for team in server.teams:
            session.delete(team)
        session.commit()

        if not erase_all_teams:
            # then create new ones
            server.teams = [Team(name=name) for name in set(params)]  # type: ignore
            session.commit()

        await safe_react_ok(message)

    async def spellbot_power(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params or params[0].lower() not in ["on", "off"]:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_power_bad",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        setting = params[0].lower()
        server.power_enabled = setting == "on"  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_power",
                reply=message.author.mention,
                setting=setting,
            ),
        )
        await safe_react_ok(message)

    async def spellbot_voice(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params or params[0].lower() not in ["on", "off"]:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_voice_bad",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        setting = params[0].lower()
        server.create_voice = setting == "on"  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_voice",
                reply=message.author.mention,
                setting=setting,
            ),
        )
        await safe_react_ok(message)

    async def spellbot_tags(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        tags_enabled = not any(param.lower() == "off" for param in params)
        channel_mentions: list[MentionableChannelType] = cast(
            list, message.channel_mentions
        )

        if message.channel_mentions:
            for mention in channel_mentions:
                channel_settings = self.ensure_channel_settings_exists(
                    session, server, mention.id, mention.name
                )
                channel_settings.tags_enabled = tags_enabled  # type: ignore
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_tags_channels",
                    reply=message.author.mention,
                    channels=", ".join(f"<#{m.id}>" for m in channel_mentions),
                    setting="on" if tags_enabled else "off",
                ),
            )
        else:
            server.tags_enabled = tags_enabled  # type: ignore
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_tags_server",
                    reply=message.author.mention,
                    setting="on" if tags_enabled else "off",
                ),
            )

        session.commit()
        await safe_react_ok(message)

    async def spellbot_queue_time(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        queue_time_enabled = not any(param.lower() == "off" for param in params)
        channel_mentions: list[MentionableChannelType] = cast(
            list, message.channel_mentions
        )

        if message.channel_mentions:
            for mention in channel_mentions:
                channel_settings = self.ensure_channel_settings_exists(
                    session, server, mention.id, mention.name
                )
                channel_settings.queue_time_enabled = queue_time_enabled  # type: ignore
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_queue_time_channels",
                    reply=message.author.mention,
                    channels=", ".join(f"<#{m.id}>" for m in channel_mentions),
                    setting="on" if queue_time_enabled else "off",
                ),
            )
        else:
            server.queue_time_enabled = queue_time_enabled  # type: ignore
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_queue_time_server",
                    reply=message.author.mention,
                    setting="on" if queue_time_enabled else "off",
                ),
            )

        session.commit()
        await safe_react_ok(message)

    async def spellbot_smotd(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        motd = " ".join(params)
        reply = message.author.mention
        if len(motd) >= 255:
            await safe_send_channel(
                message.channel, s("spellbot_smotd_too_long", reply=reply)
            )
            await safe_react_error(message)
            return
        server.smotd = motd  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel, s("spellbot_smotd", reply=reply, motd=motd)
        )
        await safe_react_ok(message)

    async def spellbot_voice_category(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        category_prefix = " ".join(params)
        reply = message.author.mention
        if len(category_prefix) >= 40:
            await safe_send_channel(
                message.channel, s("spellbot_voice_category_too_long", reply=reply)
            )
            await safe_react_error(message)
            return
        if not category_prefix:
            category_prefix = VOICE_CATEGORY_PREFIX
        server.voice_category_prefix = category_prefix  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s("spellbot_voice_category", reply=reply, category=category_prefix),
        )
        await safe_react_ok(message)

    async def spellbot_cmotd(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        motd = " ".join(params)
        reply = message.author.mention
        if len(motd) >= 255:
            await safe_send_channel(
                message.channel, s("spellbot_cmotd_too_long", reply=reply)
            )
            await safe_react_error(message)
            return

        channel_settings = self.ensure_channel_settings_exists(
            session, server, message.channel.id, message.channel.name
        )
        channel_settings.cmotd = motd  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel, s("spellbot_cmotd", reply=reply, motd=motd)
        )
        await safe_react_ok(message)

    async def spellbot_motd(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_motd_none",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        motd_str = params[0].lower()
        if motd_str not in ["private", "public", "both"]:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_motd_bad",
                    reply=message.author.mention,
                    input=params[0],
                ),
            )
            await safe_react_error(message)
            return

        server.motd = motd_str  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_motd",
                reply=message.author.mention,
                setting=motd_str,
            ),
        )
        await safe_react_ok(message)

    async def spellbot_size(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_size_none",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        default_size = to_int(params[0])
        if not default_size or not (1 < default_size <= 4):
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_size_bad",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        channel_settings = self.ensure_channel_settings_exists(
            session, server, message.channel.id, message.channel.name
        )
        channel_settings.default_size = default_size  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_size",
                reply=message.author.mention,
                default_size=default_size,
            ),
        )
        await safe_react_ok(message)

    async def spellbot_toggle_verify(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        channel_settings = self.ensure_channel_settings_exists(
            session, server, message.channel.id, message.channel.name
        )
        new_setting = not channel_settings.require_verification
        channel_settings.require_verification = new_setting  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_toggle_verify",
                reply=message.author.mention,
                setting="on" if new_setting else "off",
            ),
        )
        await safe_react_ok(message)

    async def spellbot_auto_verify(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        if not params:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_auto_verify_none",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        # Blow away the current associations first, otherwise SQLAlchemy will explode.
        session.query(AutoVerifyChannel).filter_by(guild_xid=server.guild_xid).delete()

        all_channels = False
        channels = []
        for param in params:
            if param.lower() == "all":
                all_channels = True
                break

            m = re.match("<#([0-9]+)>", param)
            if not m:
                await safe_send_channel(
                    message.channel,
                    s(
                        "spellbot_auto_verify_warn",
                        reply=message.author.mention,
                        param=param,
                    ),
                )
                continue

            discord_channel = await safe_fetch_channel(self, int(m[1]), server.guild_xid)
            if not discord_channel:
                await safe_send_channel(
                    message.channel,
                    s(
                        "spellbot_auto_verify_warn",
                        reply=message.author.mention,
                        param=param,
                    ),
                )
                continue

            channel = AutoVerifyChannel(
                channel_xid=discord_channel.id, guild_xid=server.guild_xid
            )
            session.add(channel)
            channels.append(channel)
            session.commit()

        if all_channels:
            server.auto_verify_channels = []  # type: ignore
            session.commit()
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_auto_verify",
                    reply=message.author.mention,
                    channels="all channels",
                ),
            )
        elif channels:
            server.auto_verify_channels = channels  # type: ignore
            session.commit()
            channels_str = ", ".join([f"<#{c.channel_xid}>" for c in channels])
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_auto_verify",
                    reply=message.author.mention,
                    channels=channels_str,
                ),
            )
        await safe_react_ok(message)

    async def spellbot_unverified_only(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        # Blow away the current associations first, otherwise SQLAlchemy will explode.
        session.query(UnverifiedOnlyChannel).filter_by(
            guild_xid=server.guild_xid
        ).delete()

        channels = []
        for param in params:
            m = re.match("<#([0-9]+)>", param)
            if not m:
                await safe_send_channel(
                    message.channel,
                    s(
                        "spellbot_unverified_only_warn",
                        reply=message.author.mention,
                        param=param,
                    ),
                )
                return

            discord_channel = await safe_fetch_channel(self, int(m[1]), server.guild_xid)
            if not discord_channel:
                await safe_send_channel(
                    message.channel,
                    s(
                        "spellbot_unverified_only_warn",
                        reply=message.author.mention,
                        param=param,
                    ),
                )
                return

            channel = UnverifiedOnlyChannel(
                channel_xid=discord_channel.id, guild_xid=server.guild_xid
            )
            session.add(channel)
            channels.append(channel)
            session.commit()

        server.unverified_only_channels = channels  # type: ignore
        session.commit()
        channels_str = ", ".join([f"<#{c.channel_xid}>" for c in channels])
        await safe_send_channel(
            message.channel,
            s(
                "spellbot_unverified_only",
                reply=message.author.mention,
                channels=channels_str,
            ),
        )
        await safe_react_ok(message)

    async def spellbot_verify_message(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        msg = " ".join(params)
        reply = message.author.mention
        if len(msg) >= 255:
            await safe_send_channel(
                message.channel, s("spellbot_verify_message_too_long", reply=reply)
            )
            await safe_react_error(message)
            return

        channel_settings = self.ensure_channel_settings_exists(
            session, server, message.channel.id, message.channel.name
        )
        channel_settings.verify_message = msg  # type: ignore
        session.commit()
        await safe_send_channel(
            message.channel, s("spellbot_verify_message", reply=reply, msg=msg)
        )
        await safe_react_ok(message)

    async def spellbot_awards(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        reply = message.author.mention
        if not message.attachments:
            await safe_send_channel(
                message.channel,
                s("spellbot_awards_no_data", reply=message.author.mention),
            )
            await safe_react_error(message)
            return

        bdata = await message.attachments[0].read()
        try:
            sdata = self.decode_data(bdata)
        except UnicodeDecodeError:
            await safe_send_channel(
                message.channel,
                s(
                    "spellbot_awards_not_utf",
                    reply=message.author.mention,
                ),
            )
            await safe_react_error(message)
            return

        reader = csv.reader(StringIO(sdata))
        awards = []
        for i, row in enumerate(reader):
            if len(row) != 3:
                await safe_send_channel(
                    message.channel, s("spellbot_awards_bad_row", i=i + 1, reply=reply)
                )
                await safe_react_error(message)
                return

            repeating = False
            count_str, role, msg = row
            if count_str.startswith("%"):
                repeating = True
                count_str = count_str[1:]
            count: int = int(count_str)
            if count <= 0 or math.isinf(count) or math.isnan(count):
                await safe_send_channel(
                    message.channel, s("spellbot_awards_bad_count", i=i + 1, reply=reply)
                )
                await safe_react_error(message)
                return
            if len(msg) < 5 or len(msg) >= 255:
                await safe_send_channel(
                    message.channel,
                    s("spellbot_awards_message_bad_size", i=i + 1, reply=reply),
                )
                await safe_react_error(message)
                return
            if len(role) < 1 or len(role) >= 60:
                await safe_send_channel(
                    message.channel,
                    s("spellbot_awards_role_too_long", i=i + 1, reply=reply),
                )
                await safe_react_error(message)
                return

            awards.append(
                Award(
                    guild_xid=server.guild_xid,
                    count=count,
                    repeating=repeating,
                    role=role,
                    message=msg,
                )
            )

        # Blow away the current awards first
        session.query(Award).filter_by(guild_xid=server.guild_xid).delete()
        session.commit()

        session.add_all(awards)
        session.commit()
        await safe_react_ok(message)

    async def spellbot_stats(
        self,
        session: Session,
        server: Server,
        params: List[str],
        message: discord.Message,
    ) -> None:
        from itertools import groupby
        from operator import itemgetter

        export_file = TMP_DIR / f"stats-{message.channel.guild.name}.csv"
        with open(export_file, "w") as f, redirect_stdout(f):
            print("date,channel,games")  # noqa: T001
            stats = Game.games_per_day_per_channel(session, message.channel.guild.id)
            for day, day_rows in groupby(stats, itemgetter(0)):
                for channel, row in groupby(day_rows, itemgetter(1)):
                    count = [*row][0][2]
                    print(f"{day},<#{channel}>,{count}")  # noqa: T001
        await safe_send_channel(message.channel, "", file=discord.File(export_file))
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
            channels_str = "All"
        embed.add_field(name="Active channels", value=channels_str)
        embed.add_field(name="Links privacy", value=server.links.title())
        embed.add_field(
            name="Spectator links", value="On" if server.show_spectate_link else "Off"
        )
        embed.add_field(name="MOTD privacy", value=str(server.motd).title())
        embed.add_field(name="Power", value="On" if server.power_enabled else "Off")
        embed.add_field(name="Tags", value="On" if server.tags_enabled else "Off")
        embed.add_field(
            name="Voice channels",
            value="On" if server.create_voice else "Off",
        )
        av_channels = sorted(
            server.auto_verify_channels, key=lambda channel: channel.channel_xid
        )
        if av_channels:
            av_channels_str = ", ".join(
                f"<#{channel.channel_xid}>" for channel in av_channels
            )
        else:
            av_channels_str = "All"
        embed.add_field(name="Auto verify channels", value=av_channels_str)
        uo_channels = sorted(
            server.unverified_only_channels, key=lambda channel: channel.channel_xid
        )
        if uo_channels:
            uo_channels_str = ", ".join(
                f"<#{channel.channel_xid}>" for channel in uo_channels
            )
        else:
            uo_channels_str = "None"
        embed.add_field(name="Unverified only channels", value=uo_channels_str)
        if server.teams:
            teams_str = ", ".join(sorted(team.name for team in server.teams))
            embed.add_field(name="Teams", value=teams_str)
        embed.add_field(name="Server MOTD", value=server.smotd or "None", inline=False)
        embed.add_field(
            name="Admin created voice category prefix",
            value=server.voice_category_prefix or VOICE_CATEGORY_PREFIX,
            inline=False,
        )
        embed.color = discord.Color(0x5A3EFD)
        embed.set_footer(text=f"Config for Guild ID: {server.guild_xid}")
        await safe_send_channel(message.channel, embed=embed)
        await safe_react_ok(message)

        async def warn_about_permissions(channel: discord.TextChannel, options=None):
            if channel is None:
                return
            if options is None:
                options = {
                    "read_messages",
                    "manage_messages",
                    "add_reactions",
                }
            perms = message.channel.guild.me.permissions_in(channel)
            for perm in options:
                if not getattr(perms, perm):
                    await safe_send_channel(
                        message.channel,
                        s(
                            f"warning_permissions_no_{perm}",
                            channel=f"<#{channel.id}>",
                        ),
                    )

        await warn_about_permissions(message.channel)

        for chan in channels:
            channel = await safe_fetch_channel(self, chan.channel_xid, server.guild_xid)
            if channel is None or not isinstance(channel, discord.TextChannel):
                continue
            await warn_about_permissions(channel)

        for chan in av_channels:  # type: ignore
            channel = await safe_fetch_channel(self, chan.channel_xid, server.guild_xid)
            if channel is None or not isinstance(channel, discord.TextChannel):
                continue
            await warn_about_permissions(channel, {"read_messages"})

    async def spellbot_help(
        self, prefix: str, params: List[str], message: discord.Message
    ) -> None:
        await self.help(prefix, params, message)


def get_db_env(fallback: str) -> str:
    """Returns the database env var from the environment or else the given fallback."""
    value = getenv("SPELLBOT_DB_ENV", fallback)
    return value or fallback


def get_db_url(database_env: str, fallback: str) -> str:
    """Returns the database url from the environment or else the given fallback."""
    value = getenv(database_env, fallback)
    return value or fallback


def get_port_env(fallback: str) -> str:
    """Returns the port env var from the environment or else the given fallback."""
    value = getenv("SPELLBOT_PORT_ENV", fallback)
    return value or fallback


def get_port(port_env: str, fallback: int) -> int:
    """Returns the port from the environment or else the given fallback."""
    value = getenv(port_env, fallback)
    return int(value) or fallback


def get_host(fallback: str) -> str:
    """Returns the hostname from the environment or else the given fallback."""
    value = getenv("SPELLBOT_HOST", fallback)
    return value or fallback


def get_log_level(fallback: str) -> str:
    """Returns the log level from the environment or else the given gallback."""
    value = getenv("SPELLBOT_LOG_LEVEL", fallback)
    return value or fallback


def get_redis_url() -> Optional[str]:
    """Gets redis cloud url if your REDISCLOUD_URL env var has been set."""
    return getenv("REDISCLOUD_URL", None)


async def ping(request) -> Response:
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
    if database_url.startswith("postgres://"):
        # SQLAlchemy 1.4.x removed support for the postgres:// URI scheme
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    port_env = get_port_env(port_env)
    port = get_port(port_env, port)
    host = get_host(host)
    log_level = get_log_level(log_level)
    redis_url = get_redis_url()

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

    # server for web api
    loop = asyncio.get_event_loop()
    app = web.Application()
    app.router.add_get("/", ping)

    client = SpellBot(
        token=token,
        auth=auth,
        db_url=database_url,
        redis_url=redis_url,
        log_level="DEBUG" if verbose else log_level,
        mock_games=mock_games,
        loop=loop,
    )

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, host, port)
    loop.run_until_complete(site.start())
    logger.info(f"server running: http://{host}:{port}")

    client.run()


if __name__ == "__main__":
    main()
