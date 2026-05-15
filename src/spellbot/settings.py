from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from discord import Object
from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .environment import running_in_pytest

if TYPE_CHECKING:
    from discord.abc import Snowflake


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    # Content URLs
    CONTENT_ROOT: str = "https://raw.githubusercontent.com/lexicalunit"
    SUBSCRIBE_LINK: str = "https://www.patreon.com/lexicalunit"
    DONATE_LINK: str = "https://ko-fi.com/lexicalunit"

    # Application
    BOT_TOKEN: str | None = None
    BOT_APPLICATION_ID: str | None = None
    PORT: int = 3008
    HOST: str = "localhost"
    DEBUG_GUILD: str | None = None
    API_BASE_URL: str = "https://bot.spellbot.io"
    OWNER_XID: int | None = None
    SECRET_TOKEN: str | None = None
    CHECK_SIGNATURE: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"

    # Runtime
    DISABLE_UVLOOP: bool = False

    # Datadog
    DD_API_KEY: str | None = None
    DD_APP_KEY: str | None = None
    DD_TRACE_ENABLED: bool = True
    DD_ENV: str = "dev"

    # Database
    DATABASE_URL: str | None = None
    DATABASE_POOL_SIZE: int = 20
    DATABASE_POOL_MAX_OVERFLOW: int = 40
    DATABASE_POOL_RECYCLE_S: int = 1800
    DATABASE_ECHO: bool = False

    # Cache
    REDIS_URL: str | None = None

    # TableStream
    TABLESTREAM_ROOT: str = "https://api.table-stream.com"
    TABLESTREAM_AUTH_KEY: str | None = None
    TABLESTREAM_CREATE: str = ""  # Derived from TABLESTREAM_ROOT in model_validator

    # Convoke
    CONVOKE_ROOT: str = "https://api.convoke.games/api"
    CONVOKE_API_KEY: str | None = None

    # EDHLAB
    EDHLAB_API_KEY: str | None = None
    EDHLAB_ROOT: str = "https://wmlcambifdkwygvwnpas.supabase.co"
    EDHLAB_CREATE: str = ""  # Derived from EDHLAB_ROOT in model_validator

    # Playgroup Live
    PLAYGROUP_LIVE_API_URL: str = "https://playgroup.gg"
    PLAYGROUP_LIVE_API_KEY: str | None = None

    # Bot configuration
    BOT_INVITE_LINK: str = (
        "https://discord.com/api/oauth2/authorize"
        "?client_id=725510263251402832"
        "&permissions=2416045137"
        "&scope=applications.commands%20bot"
    )
    INFO_EMBED_COLOR: int = 0x5A3EFD
    STARTED_EMBED_COLOR: int = 0xF8AE4A
    PENDING_EMBED_COLOR: int = 0x5A3EFD
    EMPTY_EMBED_COLOR: int = 0xCDCDCD
    ADMIN_ROLE: str = "SpellBot Admin"
    MOD_PREFIX: str = "Moderator"
    MAX_PENDING_GAMES: int = 5
    LOCALE: str = "en"

    # Task intervals
    VOICE_GRACE_PERIOD_M: int = 10
    VOICE_AGE_LIMIT_H: int = 5
    VOICE_CLEANUP_LOOP_M: int = 30
    VOICE_CLEANUP_BATCH: int = 30
    EXPIRE_GAMES_LOOP_M: int = 10
    EXPIRE_TIME_M: int = 45
    SHARD_STATUS_UPDATE_INTERVAL_S: int = 30

    # Patreon
    PATREON_TOKEN: str | None = None
    PATREON_CAMPAIGN: str | None = None
    PATREON_SYNC_LOOP_M: int = 60

    # Girudo
    GIRUDO_BASE_URL: str = "https://game.girudo.com"
    GIRUDO_AUTH_URL: str = "https://game.girudo.com/auth-service/api/v1/login"
    GIRUDO_LOBBY_URL: str = "https://game.girudo.com/game-service/v1/game/lobby?limit=15&offset=0"
    GIRUDO_CREATE_URL: str = "https://game.girudo.com/game-service/v1/game/multiplayer"
    GIRUDO_EMAILS: str | None = None
    GIRUDO_PASSWORDS: str | None = None
    GIRUDO_DEFAULT_FORMAT_UUID: str | None = None
    GIRUDO_DEFAULT_FORMAT_NAME: str = "Commander / EDH"
    GIRUDO_DEFAULT_TCG_UUID: str | None = None
    GIRUDO_DEFAULT_TCG_NAME: str = "Magic The Gathering"
    GIRUDO_STORE_DATA_URL: str = "https://game.girudo.com/user-service/api/v1/store-data"
    GIRUDO_RETRY_ATTEMPTS: int = 2
    GIRUDO_TIMEOUT_S: int = 10
    GIRUDO_DEFAULT_TCG_MAGIC_UUID: str | None = None

    # Not from environment - set during validation
    _database_url_resolved: str | None = None

    @model_validator(mode="after")
    def resolve_derived_urls(self) -> Settings:
        """Build derived URLs from base URLs."""
        # Resolve database URL with proper driver prefix
        url = self.DATABASE_URL or f"postgresql://postgres@{self.HOST}:5432/postgres"

        # Always use a separate test database when running in pytest
        if running_in_pytest() and not url.endswith("-test"):  # pragma: no cover
            url += "-test"

        # SQLAlchemy 1.4.x removed support for the postgres:// URI scheme
        if url.startswith("postgres://"):  # pragma: no cover
            url = url.replace("postgres://", "postgresql://", 1)
        # Ensure that we're asking for the psycopg3+ driver (and not psycopg2)
        if url.startswith("postgresql://"):  # pragma: no cover
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)

        object.__setattr__(self, "_database_url_resolved", url)

        # Derive TABLESTREAM_CREATE if not explicitly set
        if not self.TABLESTREAM_CREATE:
            object.__setattr__(
                self,
                "TABLESTREAM_CREATE",
                f"{self.TABLESTREAM_ROOT}/create-room",
            )

        # Derive EDHLAB_CREATE if not explicitly set
        if not self.EDHLAB_CREATE:
            object.__setattr__(
                self,
                "EDHLAB_CREATE",
                f"{self.EDHLAB_ROOT}/functions/v1/create-spellbot-game",
            )

        return self

    @computed_field
    @property
    def RESOLVED_DATABASE_URL(self) -> str:
        """The database URL with proper driver prefix applied."""
        return self._database_url_resolved or ""

    def workaround_over_eager_caching(self, url: str) -> str:
        return f"{url}?{datetime.now(tz=UTC).date().strftime('%Y-%m-%d')}"

    @property
    def ICO_URL(self) -> str:
        return self.workaround_over_eager_caching(
            f"{self.CONTENT_ROOT}/spellbot/main/spellbot-sm.png",
        )

    @property
    def THUMB_URL(self) -> str:
        return self.workaround_over_eager_caching(
            f"{self.CONTENT_ROOT}/spellbot/main/spellbot.png",
        )

    def queer(self, guild_xid: int | None) -> bool:  # pragma: no cover
        return (
            guild_xid
            in [
                757455940009328670,  # Oath of the Gaywatch
                699775410082414733,  # Development
            ]
            or datetime.now(tz=UTC).month == 6
        )

    @property
    def QUEER_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://spellbot.io/assets/img/logos/spellbot-lgbtq.png",
        )

    def black(self, guild_xid: int | None) -> bool:  # pragma: no cover
        return datetime.now(tz=UTC).month == 2

    @property
    def BLACK_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://spellbot.io/assets/img/logos/spellbot-black.png",
        )

    def trans(self, guild_xid: int | None) -> bool:  # pragma: no cover
        now = datetime.now(tz=UTC)
        return now.month == 11 or (now.month == 3 and now.day == 31)

    @property
    def TRANS_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://spellbot.io/assets/img/logos/spellbot-trans.png",
        )

    def autistic(self, guild_xid: int | None) -> bool:  # pragma: no cover
        now = datetime.now(tz=UTC)
        return now.month == 4 and now.day == 2

    @property
    def AUTISTIC_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://spellbot.io/assets/img/logos/spellbot-autistic.png",
        )

    def convoke(self, guild_xid: int | None) -> bool:  # pragma: no cover
        return guild_xid == 1417960690110697504  # Convoke

    @property
    def CONVOKE_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://spellbot.io/assets/img/servers/convoke.png",
        )

    def thumb(self, guild_xid: int | None) -> str:  # pragma: no cover
        if self.convoke(guild_xid):
            return settings.CONVOKE_THUMB_URL
        if self.autistic(guild_xid):
            return settings.AUTISTIC_THUMB_URL
        if settings.trans(guild_xid):
            return settings.TRANS_THUMB_URL
        if settings.queer(guild_xid):
            return settings.QUEER_THUMB_URL
        if settings.black(guild_xid):
            return settings.BLACK_THUMB_URL
        return settings.THUMB_URL

    @property
    def GUILD_OBJECT(self) -> Snowflake | None:
        return Object(id=self.DEBUG_GUILD) if self.DEBUG_GUILD else None


settings = Settings()
