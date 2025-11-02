from __future__ import annotations

from datetime import UTC, datetime
from os import getenv
from typing import TYPE_CHECKING

from discord import Object

from .environment import running_in_pytest

if TYPE_CHECKING:
    from discord.abc import Snowflake


class Settings:
    __slots__ = (
        "ADMIN_ROLE",
        "API_BASE_URL",
        "BOT_APPLICATION_ID",
        "BOT_INVITE_LINK",
        "BOT_TOKEN",
        "CONTENT_ROOT",
        "CONVOKE_API_KEY",
        "CONVOKE_ROOT",
        "DATABASE_ECHO",
        "DATABASE_URL",
        "DD_API_KEY",
        "DD_APP_KEY",
        "DD_TRACE_ENABLED",
        "DEBUG_GUILD",
        "DONATE_LINK",
        "EMPTY_EMBED_COLOR",
        "EXPIRE_GAMES_LOOP_M",
        "EXPIRE_TIME_M",
        "HOST",
        "INFO_EMBED_COLOR",
        "LOCALE",
        "MAX_PENDING_GAMES",
        "MOD_PREFIX",
        "OWNER_XID",
        "PATREON_CAMPAIGN",
        "PATREON_SYNC_LOOP_M",
        "PATREON_TOKEN",
        "PENDING_EMBED_COLOR",
        "PORT",
        "REDIS_URL",
        "SPELLTABLE_API_KEY",
        "SPELLTABLE_AUTH_REDIRECT",
        "SPELLTABLE_CLIENT_ID",
        "SPELLTABLE_PASSES",
        "SPELLTABLE_ROOT",
        "SPELLTABLE_USERS",
        "STARTED_EMBED_COLOR",
        "SUBSCRIBE_LINK",
        "TABLESTREAM_AUTH_KEY",
        "TABLESTREAM_CREATE",
        "TABLESTREAM_ROOT",
        "VOICE_AGE_LIMIT_H",
        "VOICE_CLEANUP_BATCH",
        "VOICE_CLEANUP_LOOP_M",
        "VOICE_GRACE_PERIOD_M",
        "WIZARDS_ROOT",
        "guild_xid",
    )

    def __init__(self, guild_xid: int | None = None) -> None:  # noqa: PLR0915
        self.guild_xid = guild_xid

        # content
        self.CONTENT_ROOT = "https://raw.githubusercontent.com/lexicalunit"
        self.SUBSCRIBE_LINK = "https://www.patreon.com/lexicalunit"
        self.DONATE_LINK = "https://ko-fi.com/lexicalunit"

        # application
        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.BOT_APPLICATION_ID = getenv("BOT_APPLICATION_ID")
        self.PORT = int(getenv("PORT", "3008"))
        self.HOST = getenv("HOST") or "localhost"
        self.DEBUG_GUILD = getenv("DEBUG_GUILD")
        self.API_BASE_URL = getenv("API_BASE_URL", "https://bot.spellbot.io")
        self.OWNER_XID = getenv("OWNER_XID")

        # datadog
        self.DD_API_KEY = getenv("DD_API_KEY")
        self.DD_APP_KEY = getenv("DD_APP_KEY")
        self.DD_TRACE_ENABLED = getenv("DD_TRACE_ENABLED", "true").lower() == "true"

        # database
        default_database_url = f"postgresql://postgres@{self.HOST}:5432/postgres"
        if running_in_pytest():  # pragma: no cover
            default_database_url += "-test"
        database_url = getenv("DATABASE_URL") or default_database_url
        if database_url.startswith("postgres://"):  # pragma: no cover
            # SQLAlchemy 1.4.x removed support for the postgres:// URI scheme
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        if database_url.startswith("postgresql://"):  # pragma: no cover
            # Ensure that we're asking for the psycopg3+ driver (and not psycopg2)
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.DATABASE_URL = database_url

        # cache
        self.REDIS_URL = getenv("REDIS_URL")

        # spelltable
        self.WIZARDS_ROOT = getenv("WIZARDS_ROOT", "https://myaccounts.wizards.com")
        self.SPELLTABLE_ROOT = getenv(
            "SPELLTABLE_ROOT",
            "https://xgaqvxzggl.execute-api.us-west-2.amazonaws.com",
        )
        self.SPELLTABLE_USERS = getenv("SPELLTABLE_USERS")
        self.SPELLTABLE_PASSES = getenv("SPELLTABLE_PASSES")
        self.SPELLTABLE_API_KEY = getenv("SPELLTABLE_API_KEY")
        self.SPELLTABLE_CLIENT_ID = getenv("SPELLTABLE_CLIENT_ID")
        self.SPELLTABLE_AUTH_REDIRECT = getenv(
            "SPELLTABLE_AUTH_REDIRECT",
            "https://spelltable.wizards.com/auth/authorize",
        )

        # tablestream
        self.TABLESTREAM_ROOT = "https://api.table-stream.com"
        self.TABLESTREAM_CREATE = f"{self.TABLESTREAM_ROOT}/create-room"
        self.TABLESTREAM_AUTH_KEY = getenv("TABLESTREAM_AUTH_KEY")

        # convoke
        self.CONVOKE_ROOT = "https://api.convoke.games/api"
        self.CONVOKE_API_KEY = getenv("CONVOKE_API_KEY")

        # configuration
        self.BOT_INVITE_LINK = (
            r"https://discordapp.com/api/oauth2/authorize"
            r"?client_id=725510263251402832"
            r"&permissions=2416045137"
            r"&scope=applications.commands%20bot"
        )
        self.INFO_EMBED_COLOR = 0x5A3EFD
        self.STARTED_EMBED_COLOR = 0xF8AE4A
        self.PENDING_EMBED_COLOR = 0x5A3EFD
        self.EMPTY_EMBED_COLOR = 0xCDCDCD
        self.DATABASE_ECHO = False
        self.ADMIN_ROLE = "SpellBot Admin"
        self.MOD_PREFIX = "Moderator"
        self.MAX_PENDING_GAMES = 5
        self.LOCALE = getenv("LOCALE", "en")

        # tasks
        self.VOICE_GRACE_PERIOD_M = 10  # 10 minutes
        self.VOICE_AGE_LIMIT_H = 5  # 5 hours
        self.VOICE_CLEANUP_LOOP_M = 30  # 30 minutes
        self.VOICE_CLEANUP_BATCH = 30  # batch size
        self.EXPIRE_GAMES_LOOP_M = 10  # 10 minutes
        self.EXPIRE_TIME_M = 45  # 45 minutes

        # patreon integration
        self.PATREON_TOKEN = getenv("PATREON_TOKEN")
        self.PATREON_CAMPAIGN = getenv("PATREON_CAMPAIGN")
        self.PATREON_SYNC_LOOP_M = 60  # 60 minutes

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
                # 699775410082414733,  # Development
            ]
            or datetime.now(tz=UTC).month == 6
        )

    @property
    def QUEER_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://user-images.githubusercontent.com/1903876/"
            "149257079-e3efe74f-482b-4410-a0ea-dd988a4d3c63.png",
        )

    def black(self, guild_xid: int | None) -> bool:  # pragma: no cover
        return datetime.now(tz=UTC).month == 2

    @property
    def BLACK_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://github.com/user-attachments/assets/146f40fd-1d8a-4027-937a-b00799ce89bc",
        )

    @property
    def TRANS_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://github.com/user-attachments/assets/cb469ae7-5a31-4855-9510-03762e204b52",
        )

    def trans(self, guild_xid: int | None) -> bool:  # pragma: no cover
        now = datetime.now(tz=UTC)
        return now.month == 11 or (now.month == 3 and now.day == 31)

    @property
    def WOMEN_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://github.com/user-attachments/assets/b66f40cc-d2c7-49eb-880a-c8965d94d412",
        )

    def women(self, guild_xid: int | None) -> bool:  # pragma: no cover
        return datetime.now(tz=UTC).month == 3

    @property
    def AUTISTIC_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://github.com/user-attachments/assets/e2799f26-6873-452a-97a4-e25a64d6d991",
        )

    def autistic(self, guild_xid: int | None) -> bool:  # pragma: no cover
        now = datetime.now(tz=UTC)
        return now.month == 4 and now.day == 2

    def thumb(self, guild_xid: int | None) -> str:  # pragma: no cover
        if self.autistic(guild_xid):
            return settings.AUTISTIC_THUMB_URL
        if settings.trans(guild_xid):
            return settings.TRANS_THUMB_URL
        if settings.women(guild_xid):
            return settings.WOMEN_THUMB_URL
        if settings.queer(guild_xid):
            return settings.QUEER_THUMB_URL
        if settings.black(guild_xid):
            return settings.BLACK_THUMB_URL
        return settings.THUMB_URL

    @property
    def GUILD_OBJECT(self) -> Snowflake | None:
        return Object(id=self.DEBUG_GUILD) if self.DEBUG_GUILD else None


settings = Settings()
