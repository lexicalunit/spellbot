# pylint: disable=too-many-instance-attributes
from __future__ import annotations

from datetime import datetime
from os import getenv
from typing import Optional

from discord import Object
from discord.abc import Snowflake

from .environment import running_in_pytest


class Settings:
    def __init__(self, guild_xid: Optional[int] = None):
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
        self.VOICE_INVITE_EXPIRE_TIME_S = 14400  # 4 hours
        self.EMBED_COLOR = 0x5A3EFD
        self.DATABASE_ECHO = False
        self.ADMIN_ROLE = "SpellBot Admin"
        self.MOD_PREFIX = "Moderator"

        # tasks
        self.VOICE_GRACE_PERIOD_M = 10  # 10 minutes
        self.VOICE_AGE_LIMIT_H = 5  # 5 hours
        self.VOICE_CLEANUP_LOOP_M = 30  # 30 minutes
        self.VOICE_CLEANUP_BATCH = 30  # batch size
        self.EXPIRE_GAMES_LOOP_M = 10  # 10 minutes
        self.EXPIRE_TIME_M = 45  # 45 minutes

    def workaround_over_eager_caching(self, url: str) -> str:
        return f"{url}?{datetime.today().strftime('%Y-%m-%d')}"

    @property
    def THUMB_URL(self) -> str:
        if self.guild_xid == 757455940009328670:  # pragma: no cover
            return self.workaround_over_eager_caching(
                "https://user-images.githubusercontent.com/1903876/"
                "149257079-e3efe74f-482b-4410-a0ea-dd988a4d3c63.png",
            )
        return self.workaround_over_eager_caching(
            f"{self.CONTENT_ROOT}/spellbot/main/spellbot.png",
        )

    @property
    def ICO_URL(self) -> str:
        if self.guild_xid == 757455940009328670:  # pragma: no cover
            return self.workaround_over_eager_caching(
                "https://user-images.githubusercontent.com/1903876/"
                "149257564-86595c81-82a5-4558-ae40-c03d29a95d1f.png",
            )
        return self.workaround_over_eager_caching(
            f"{self.CONTENT_ROOT}/spellbot/main/spellbot-sm.png",
        )

    @property
    def GUILD_OBJECT(self) -> Optional[Snowflake]:
        return Object(id=self.DEBUG_GUILD) if self.DEBUG_GUILD else None
