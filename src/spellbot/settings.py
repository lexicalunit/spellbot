from __future__ import annotations

from datetime import datetime
from os import getenv
from typing import TYPE_CHECKING

import pytz
from discord import Object

from .environment import running_in_pytest

if TYPE_CHECKING:
    from discord.abc import Snowflake


class Settings:
    __slots__ = (
        "guild_xid",
        "CONTENT_ROOT",
        "BOT_TOKEN",
        "BOT_APPLICATION_ID",
        "PORT",
        "HOST",
        "DEBUG_GUILD",
        "API_BASE_URL",
        "DD_API_KEY",
        "DD_APP_KEY",
        "DD_TRACE_ENABLED",
        "DATABASE_URL",
        "SPELLTABLE_ROOT",
        "SPELLTABLE_CREATE",
        "SPELLTABLE_AUTH_KEY",
        "BOT_INVITE_LINK",
        "INFO_EMBED_COLOR",
        "STARTED_EMBED_COLOR",
        "PENDING_EMBED_COLOR",
        "EMPTY_EMBED_COLOR",
        "DATABASE_ECHO",
        "ADMIN_ROLE",
        "MOD_PREFIX",
        "MAX_PENDING_GAMES",
        "VOICE_GRACE_PERIOD_M",
        "VOICE_AGE_LIMIT_H",
        "VOICE_CLEANUP_LOOP_M",
        "VOICE_CLEANUP_BATCH",
        "EXPIRE_GAMES_LOOP_M",
        "EXPIRE_TIME_M",
    )

    def __init__(self, guild_xid: int | None = None) -> None:
        self.guild_xid = guild_xid

        # content
        self.CONTENT_ROOT = "https://raw.githubusercontent.com/lexicalunit"

        # application
        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.BOT_APPLICATION_ID = getenv("BOT_APPLICATION_ID")
        self.PORT = int(getenv("PORT", "3008"))
        self.HOST = getenv("HOST") or "localhost"
        self.DEBUG_GUILD = getenv("DEBUG_GUILD")
        self.API_BASE_URL = getenv("API_BASE_URL", "https://bot.spellbot.io")

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
        self.DATABASE_URL = database_url

        # spelltable
        self.SPELLTABLE_ROOT = "https://us-central1-magic-night-30324.cloudfunctions.net"
        self.SPELLTABLE_CREATE = f"{self.SPELLTABLE_ROOT}/createGame"
        self.SPELLTABLE_AUTH_KEY = getenv("SPELLTABLE_AUTH_KEY")

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

        # tasks
        self.VOICE_GRACE_PERIOD_M = 10  # 10 minutes
        self.VOICE_AGE_LIMIT_H = 5  # 5 hours
        self.VOICE_CLEANUP_LOOP_M = 30  # 30 minutes
        self.VOICE_CLEANUP_BATCH = 30  # batch size
        self.EXPIRE_GAMES_LOOP_M = 10  # 10 minutes
        self.EXPIRE_TIME_M = 45  # 45 minutes

    def workaround_over_eager_caching(self, url: str) -> str:
        return f"{url}?{datetime.now(tz=pytz.utc).date().strftime('%Y-%m-%d')}"

    def queer(self, guild_xid: int | None) -> bool:
        return (
            guild_xid
            in [
                757455940009328670,  # Oath of the Gaywatch
                699775410082414733,  # Development
            ]
            or datetime.now(tz=pytz.utc).month == 6
        )

    @property
    def THUMB_URL(self) -> str:
        return self.workaround_over_eager_caching(
            f"{self.CONTENT_ROOT}/spellbot/main/spellbot.png",
        )

    @property
    def QUEER_THUMB_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://user-images.githubusercontent.com/1903876/"
            "149257079-e3efe74f-482b-4410-a0ea-dd988a4d3c63.png",
        )

    @property
    def ICO_URL(self) -> str:
        return self.workaround_over_eager_caching(
            f"{self.CONTENT_ROOT}/spellbot/main/spellbot-sm.png",
        )

    @property
    def QUEER_ICO_URL(self) -> str:  # pragma: no cover
        return self.workaround_over_eager_caching(
            "https://user-images.githubusercontent.com/1903876/"
            "149257564-86595c81-82a5-4558-ae40-c03d29a95d1f.png",
        )

    @property
    def GUILD_OBJECT(self) -> Snowflake | None:
        return Object(id=self.DEBUG_GUILD) if self.DEBUG_GUILD else None


settings = Settings()
