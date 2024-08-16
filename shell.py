#!/usr/bin/env python
from __future__ import annotations

from os import environ

environ["DISABLE_UVLOOP"] = "1"

import nest_asyncio
from asgiref.sync import async_to_sync
from IPython import embed

from spellbot.database import db_session_manager, initialize_connection


@async_to_sync()
async def runner() -> None:
    banner = ["from spellbot.database import DatabaseSession"]
    await initialize_connection("spellbot-bot", run_migrations=True)
    async with db_session_manager():
        from spellbot.database import DatabaseSession
        from spellbot.models import Base

        for m in Base.registry.mappers:  # type: ignore
            globals()[m.class_.__name__] = m.class_
            banner.append(f"from spellbot.models import {m.class_.__name__}")

        globals()["DatabaseSession"] = DatabaseSession

        embed(
            colors="neutral",
            using="asyncio",
            banner2="\n".join(banner),
        )


nest_asyncio.apply()
runner()
