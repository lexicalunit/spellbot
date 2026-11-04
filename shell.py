#!/usr/bin/env python
# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from os import environ

environ["DISABLE_UVLOOP"] = "1"

from IPython import embed
from IPython.core.async_helpers import get_asyncio_loop
from sqlalchemy import and_, asc, delete, desc, func, insert, not_, or_, select, text, update

from spellbot.database import DatabaseSession, db_session_maker, initialize_connection
from spellbot.models import Base

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


def main() -> None:
    banner = ["from spellbot.database import DatabaseSession"]
    for name, export in SQLALCHEMY_EXPORTS.items():
        globals()[name] = export
        banner.append(f"from sqlalchemy import {name}")
    for m in Base.registry.mappers:
        globals()[m.class_.__name__] = m.class_
        banner.append(f"from spellbot.models import {m.class_.__name__}")
    globals()["DatabaseSession"] = DatabaseSession

    loop = get_asyncio_loop()
    loop.run_until_complete(initialize_connection("spellbot-bot", run_migrations=True))

    token = DatabaseSession.set(db_session_maker())
    try:
        loop.run_until_complete(DatabaseSession.execute(text("SELECT 1")))
        embed(colors="neutral", using="asyncio", banner2="\n".join(banner))
        loop.run_until_complete(DatabaseSession.commit())
    finally:
        loop.run_until_complete(DatabaseSession.close())
        DatabaseSession.reset(token)


main()
