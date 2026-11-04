# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import discord
import httpx
from ddtrace.trace import tracer
from discord.ext.commands import AutoShardedBot, CommandError, CommandNotFound, Context

from . import services
from .data import GameLinkDetails
from .database import db_session_manager, initialize_connection
from .enums import GameService
from .integrations import convoke, edhlab, girudo, playgroup_live
from .metrics import add_span_request_id, generate_request_id, setup_metrics, tag_span
from .settings import settings

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from .data import GameData


logger = logging.getLogger(__name__)

# Disable pointless nacl warning log coming from discord.py.
if hasattr(discord.VoiceClient, "warn_nacl"):  # pragma: no cover
    discord.VoiceClient.warn_nacl = False


class TTLDict[K, V]:
    """Small bounded TTL dict; evicts expired entries on access and keeps size capped."""

    def __init__(self, *, maxsize: int, ttl: float) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def _purge(self) -> None:
        now = monotonic()
        for k in [k for k, (exp, _) in self._data.items() if exp <= now]:
            del self._data[k]

    def get(self, key: K) -> V | None:
        self._purge()
        item = self._data.get(key)
        if item is None:
            return None
        self._data.move_to_end(key)
        return item[1]

    def __getitem__(self, key: K) -> V:
        self._purge()
        item = self._data[key]
        self._data.move_to_end(key)
        return item[1]

    def __setitem__(self, key: K, value: V) -> None:
        self._purge()
        self._data[key] = (monotonic() + self._ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)


class SpellBot(AutoShardedBot):
    def __init__(
        self,
        mock_games: bool = False,
        disable_tasks: bool = False,
        create_connection: bool = True,
    ) -> None:
        intents = discord.Intents().default()
        logger.info("intents.value: %s", intents.value)
        kwargs: dict[str, Any] = {}
        if settings.BOT_APPLICATION_ID is not None:  # pragma: no cover
            kwargs["application_id"] = int(settings.BOT_APPLICATION_ID)
        super().__init__(command_prefix="!", help_command=None, intents=intents, **kwargs)
        self.mock_games = mock_games
        self.disable_tasks = disable_tasks
        self.create_connection = create_connection
        self.guild_locks = TTLDict[int, asyncio.Lock](maxsize=100, ttl=3600)  # 1 hr
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
        from .views import GameView  # allow_inline

        self.add_view(GameView(self))

        # load all cog extensions and application commands
        from .utils import load_extensions  # allow_inline

        await load_extensions(self)

        # ensure application emojis exist and cache them
        await self.ensure_application_emojis()

    async def ensure_application_emoji(
        self,
        name: str,
        image_bytes: bytes,
    ) -> discord.Emoji | None:
        try:
            return await self.create_application_emoji(name=name, image=image_bytes)
        except Exception:
            logger.exception("warning: could not create application emoji %s", name)
        return None

    async def ensure_application_emojis(self) -> None:
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
            return await self.ensure_application_emoji(name, image_bytes)

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
    async def guild_lock(self, guild_xid: int) -> AsyncGenerator[None]:
        if not self.guild_locks.get(guild_xid):
            self.guild_locks[guild_xid] = asyncio.Lock()
        async with self.guild_locks[guild_xid]:
            yield

    @tracer.wrap()
    async def create_game_link(
        self,
        game_data: GameData,
        pins: dict[int, str] | None = None,
        original_seats: int | None = None,
    ) -> GameLinkDetails:
        if self.mock_games:
            return GameLinkDetails(f"http://example.com/game/{uuid4()}")
        service = game_data.service
        tag_span(link_service=GameService(service).name)
        match service:
            case GameService.CONVOKE.value:
                return await convoke.generate_link(game_data, pins)
            case GameService.GIRUDO.value:
                return await girudo.generate_link(game_data)
            case GameService.EDHLAB.value:
                return await edhlab.generate_link(game_data)
            case GameService.PLAYGROUP_LIVE.value:
                return await playgroup_live.generate_link(game_data, original_seats)
            case _:
                return GameLinkDetails()

    async def update_game_players(self, game_data: GameData, pins: dict[int, str]) -> None:
        """Send the final roster and pins for a game whose link was created before it filled."""
        if self.mock_games or game_data.service != GameService.CONVOKE.value:
            return
        await convoke.update_players(game_data, pins)

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
    async def handle_message_deleted(self, message: discord.Message) -> None:
        data = await services.games.get_by_message_xid(message.id)
        if not data:
            return
        game_id = data.id
        logger.info("Game %s was deleted manually.", game_id)
        if not data.started_at:  # someone deleted a pending game
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
    setup_metrics()
    return bot
