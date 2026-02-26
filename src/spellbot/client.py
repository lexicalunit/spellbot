from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

import discord
import httpx
from cachetools import TTLCache
from ddtrace.trace import tracer
from discord.ext.commands import AutoShardedBot, CommandError, CommandNotFound, Context

from .database import db_session_manager, initialize_connection
from .enums import GameService
from .integrations import convoke, girudo, tablestream
from .metrics import add_span_request_id, generate_request_id, setup_ignored_errors, setup_metrics
from .models import GameLinkDetails
from .operations import safe_delete_message
from .services import ServicesRegistry
from .settings import settings
from .utils import user_can_moderate

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from .models import GameDict


logger = logging.getLogger(__name__)

# Disable pointless nacl warning log coming from discord.py.
if hasattr(discord.VoiceClient, "warn_nacl"):  # pragma: no cover
    discord.VoiceClient.warn_nacl = False


class SpellBot(AutoShardedBot):
    def __init__(
        self,
        mock_games: bool = False,
        disable_tasks: bool = False,
        create_connection: bool = True,
    ) -> None:
        intents = discord.Intents().default()
        intents.members = True
        intents.message_content = True
        intents.messages = True
        logger.info("intents.value: %s", intents.value)
        kwargs = {}
        if settings.BOT_APPLICATION_ID is not None:  # pragma: no cover
            kwargs["application_id"] = int(settings.BOT_APPLICATION_ID)
        super().__init__(command_prefix="!", help_command=None, intents=intents, **kwargs)
        self.mock_games = mock_games
        self.disable_tasks = disable_tasks
        self.create_connection = create_connection
        self.guild_locks = TTLCache[int, asyncio.Lock](maxsize=100, ttl=3600)  # 1 hr
        self.supporters: set[int] = set()
        self.ready_shards: set[int] = set()
        self.emojis_cache: list[discord.PartialEmoji | discord.Emoji] = []

    async def on_ready(self) -> None:  # pragma: no cover
        logger.info("client ready")

    async def on_shard_ready(self, shard_id: int) -> None:  # pragma: no cover
        logger.info("shard %s ready", shard_id)
        self.ready_shards.add(shard_id)

    async def on_shard_disconnect(self, shard_id: int) -> None:  # pragma: no cover
        logger.info("shard %s disconnected", shard_id)
        self.ready_shards.discard(shard_id)

    async def on_shard_resumed(self, shard_id: int) -> None:  # pragma: no cover
        logger.info("shard %s resumed", shard_id)
        self.ready_shards.add(shard_id)

    async def setup_hook(self) -> None:  # pragma: no cover
        # Note: In tests we create the connection using fixtures.
        if self.create_connection:  # pragma: no cover
            logger.info("initializing database connection...")
            await initialize_connection("spellbot-bot")

        # register persistent views
        from .views import GameView, SetupView  # allow_inline

        self.add_view(GameView(self))
        self.add_view(SetupView(self))

        # load all cog extensions and application commands
        from .utils import load_extensions  # allow_inline

        await load_extensions(self)

        # ensure application emojis exist and cache them
        await self._ensure_application_emojis()

    async def _create_application_emoji(
        self,
        name: str,
        image_bytes: bytes,
    ) -> discord.Emoji | None:
        try:
            return await self.create_application_emoji(name=name, image=image_bytes)
        except Exception:
            logger.exception("warning: could not create application emoji %s", name)
        return None

    async def _ensure_application_emojis(self) -> None:
        """Fetch all application emojis from Discord API, creating missing ones if needed."""

        async def fetch() -> list[discord.PartialEmoji | discord.Emoji]:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bot {settings.BOT_TOKEN}"}
                resp = await client.get(
                    f"https://discord.com/api/v10/applications/{self.application_id}/emojis",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    discord.PartialEmoji(name=item["name"], id=int(item["id"]))
                    for item in data.get("items", [])
                ]

        async def ensure(
            emojis: list[discord.PartialEmoji | discord.Emoji],
            name: str,
            image_bytes: bytes,
        ) -> discord.PartialEmoji | discord.Emoji | None:
            for emoji in emojis:
                if emoji.name == name:
                    return emoji
            return await self._create_application_emoji(name, image_bytes)

        try:
            emojis = await fetch()
            emoji_dir = ASSETS_DIR / "emoji"
            emoji_files = list(emoji_dir.glob("*.png"))
            for image_path in emoji_files:
                name = image_path.stem
                image_bytes = image_path.read_bytes()
                created = await ensure(emojis, name, image_bytes)
                if created and created not in emojis:
                    emojis.append(created)
            self.emojis_cache = emojis
            logger.info("cached %d application emojis", len(self.emojis_cache))
        except Exception:
            logger.exception("warning: could not fetch application emojis")

    @asynccontextmanager
    async def guild_lock(self, guild_xid: int) -> AsyncGenerator[None, None]:
        if not self.guild_locks.get(guild_xid):
            self.guild_locks[guild_xid] = asyncio.Lock()
        async with self.guild_locks[guild_xid]:
            yield

    @tracer.wrap()
    async def create_game_link(
        self,
        game: GameDict,
        pins: list[str] | None = None,
    ) -> GameLinkDetails:
        if self.mock_games:
            return GameLinkDetails(f"http://exmaple.com/game/{uuid4()}")
        service = game.get("service")
        if span := tracer.current_span():  # pragma: no cover
            span.set_tag("link_service", GameService(service).name)
        match service:
            case GameService.CONVOKE.value:
                details = await convoke.generate_link(game, pins)
                return GameLinkDetails(*details)
            case GameService.TABLE_STREAM.value:
                details = await tablestream.generate_link(game)
                return GameLinkDetails(*details)
            case GameService.GIRUDO.value:
                details = await girudo.generate_link(game)
                return GameLinkDetails(details.link, details.password)
            case _:
                return GameLinkDetails()

    @tracer.wrap(name="interaction", resource="on_message")
    async def on_message(
        self,
        message: discord.Message,
    ) -> None:
        span = tracer.current_span()
        if span:  # pragma: no cover
            setup_ignored_errors(span)

        # Generate request ID for message events (no interaction ID available)
        request_id = generate_request_id()
        add_span_request_id(request_id)

        # handle DMs normally
        if not message.guild or not hasattr(message.guild, "id"):
            return await super().on_message(message)
        if span:  # pragma: no cover
            span.set_tag("guild_xid", str(message.guild.id))

        # ignore everything except messages in text channels
        if not hasattr(message.channel, "type") or message.channel.type != discord.ChannelType.text:
            return None
        if span:  # pragma: no cover
            span.set_tag("channel_xid", str(message.channel.id))

        # ignore hidden/ephemeral messages
        if message.flags.value & 64:
            return None

        # to verify users we need their user id
        if not hasattr(message.author, "id"):
            return None

        message_author_xid = message.author.id
        if span:
            span.set_tag("user_xid", str(message_author_xid))

        # don't try to verify the bot itself
        if self.user and message_author_xid == self.user.id:  # pragma: no cover
            return None

        async with db_session_manager():
            await self.handle_verification(message)
            return None

    @tracer.wrap(name="interaction", resource="on_message_delete")
    async def on_message_delete(self, message: discord.Message) -> None:
        # Generate request ID for message delete events (no interaction ID available)
        request_id = generate_request_id()
        add_span_request_id(request_id)

        message_xid: int | None = getattr(message, "id", None)
        if not message_xid:
            return
        async with db_session_manager():
            await self.handle_message_deleted(message)

    async def on_command_error(
        self,
        context: Context[SpellBot],
        exception: CommandError,
    ) -> None:
        if isinstance(exception, CommandNotFound):
            return None
        return await super().on_command_error(context, exception)

    @tracer.wrap()
    async def handle_verification(self, message: discord.Message) -> None:
        services = ServicesRegistry()
        message_author_xid = message.author.id
        verified: bool | None = None
        assert message.guild is not None
        await services.guilds.upsert(message.guild)
        channel_data = await services.channels.upsert(message.channel)
        if channel_data["auto_verify"]:
            verified = True
        assert message.guild
        guild: discord.Guild = message.guild
        await services.verifies.upsert(guild.id, message_author_xid, verified)
        if not user_can_moderate(message.author, guild, message.channel):
            user_is_verified = await services.verifies.is_verified()
            if user_is_verified and channel_data["unverified_only"]:
                await safe_delete_message(message)
            if not user_is_verified and channel_data["verified_only"]:
                await safe_delete_message(message)

    @tracer.wrap()
    async def handle_message_deleted(self, message: discord.Message) -> None:
        services = ServicesRegistry()
        data = await services.games.select_by_message_xid(message.id)
        if not data:
            return
        game_id = data["id"]
        logger.info("Game %s was deleted manually.", game_id)
        if not data["started_at"]:  # someone deleted a pending game
            await services.games.delete_games([game_id])


def build_bot(
    mock_games: bool = False,
    disable_tasks: bool = False,
    create_connection: bool = True,
) -> SpellBot:
    bot = SpellBot(
        mock_games=mock_games,
        disable_tasks=disable_tasks,
        create_connection=create_connection,
    )
    bot.fetch_application_emojis = AsyncMock(return_value=[])
    setup_metrics()
    return bot
