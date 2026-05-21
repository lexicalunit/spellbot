#!/usr/bin/env python
from __future__ import annotations

from os import environ

environ["DISABLE_UVLOOP"] = "1"

import asyncio

import nest_asyncio
from IPython import embed
from sqlalchemy import and_, asc, delete, desc, func, insert, not_, or_, select, text, update

from spellbot.database import db_session_manager, initialize_connection

SQLALCHEMY_EXPORTS = {
    "and_": and_,
    "asc": asc,
    "delete": delete,
    "desc": desc,
    "func": func,
    "insert": insert,
    "not_": not_,
    "or_": or_,
    "select": select,
    "text": text,
    "update": update,
}


async def runner() -> None:
    banner = ["from spellbot.database import DatabaseSession"]
    await initialize_connection("spellbot-bot", run_migrations=True)
    async with db_session_manager():
        from spellbot.database import DatabaseSession
        from spellbot.models import Base

        for name, export in SQLALCHEMY_EXPORTS.items():
            globals()[name] = export
            banner.append(f"from sqlalchemy import {name}")

        for m in Base.registry.mappers:
            globals()[m.class_.__name__] = m.class_
            banner.append(f"from spellbot.models import {m.class_.__name__}")

        globals()["DatabaseSession"] = DatabaseSession

        # Pre-warm the connection pool
        await DatabaseSession.execute(text("SELECT 1"))

        # Apply nest_asyncio only after the connection is established
        nest_asyncio.apply()

        embed(
            colors="neutral",
            using="asyncio",
            banner2="\n".join(banner),
        )


try:
    asyncio.run(runner())
except RuntimeError as exc:
    # On Python 3.14, asyncio.run()'s shutdown calls shutdown_default_executor
    # with a timeout, which requires a current task; nest_asyncio's patched
    # task tracking doesn't satisfy this on loop teardown.
    if "Timeout should be used inside a task" not in str(exc):
        raise
