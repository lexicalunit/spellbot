from __future__ import annotations

import sys
from datetime import datetime
from os import getenv
from typing import Generic, Type, TypeVar

T = TypeVar("T", bound="Singleton")


class Singleton(Generic[T], type):
    _instances: dict[Type[T], T] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(  # type: ignore
                *args,
                **kwargs,
            )

        return cls._instances[cls]  # type: ignore


class Settings(metaclass=Singleton):  # pylint: disable=R0902
    def __init__(self):
        # content
        self.CONTENT_ROOT = "https://raw.githubusercontent.com/lexicalunit"
        self.THUMB_URL = (
            f"{self.CONTENT_ROOT}/spellbot/main/spellbot.png"
            f"?{datetime.today().strftime('%Y-%m-%d')}"  # workaround over-eager caching
        )
        self.ICO_URL = (
            f"{self.CONTENT_ROOT}/spellbot/main/spellbot-sm.png"
            f"?{datetime.today().strftime('%Y-%m-%d')}"  # workaround over-eager caching
        )

        # application
        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.PORT = int(getenv("PORT", "3008"))
        self.HOST = getenv("HOST") or "localhost"
        self.DEBUG_GUILD = getenv("DEBUG_GUILD")
        self.API_BASE_URL = getenv("API_BASE_URL", "https://bot.spellbot.io")

        # database
        default_database_url = f"postgresql://postgres@{self.HOST}:5432/postgres"
        if getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:  # pragma: no cover
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
        self.EXPIRE_TIME_M = 45  # 45 minutes

        # tasks
        self.VOICE_GRACE_PERIOD_M = 10  # 10 minutes
        self.VOICE_AGE_LIMIT_H = 5  # 5 hours
        self.VOICE_CLEANUP_LOOP_M = 30  # 30 minutes
        self.VOICE_CLEANUP_BATCH = 40  # batch size
        self.EXPIRE_GAMES_LOOP_M = 10  # 10 minutes
