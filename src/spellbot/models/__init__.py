from __future__ import annotations

from importlib import import_module
from inspect import getmembers, isclass
from pathlib import Path
from pkgutil import iter_modules
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy import Table


def import_models() -> None:  # pragma: no cover
    package_dir = Path(__file__).resolve().parent
    for info in iter_modules([str(package_dir)]):
        module = import_module(f"{__name__}.{info.name}")
        for name, _object in getmembers(module, isclass):
            if isclass(_object) and issubclass(_object, Base) and name not in globals():
                globals()[name] = _object


from .base import (  # noqa: I001,E402
    WEB_EDITABLE,
    Base,
    create_all,
    literalquery,
    now,
    reverse_all,
    web_editable,
)

from .alert import Alert  # noqa: E402
from .award import GuildAward, UserAward  # noqa: E402
from .block import Block  # noqa: E402
from .channel import Channel  # noqa: E402
from .game import Game, GameStatus, MAX_RULES_LENGTH  # noqa: E402
from .guild import Guild  # noqa: E402
from .guild_member import GuildMember  # noqa: E402
from .play import Play, generate_pin  # noqa: E402
from .post import Post  # noqa: E402
from .queue import Queue  # noqa: E402
from .token import Token  # noqa: E402
from .user import User  # noqa: E402
from .verify import Verify  # noqa: E402
from .watch import Watch  # noqa: E402


class HasTable(Protocol):
    __table__: Table


def web_editable_columns(model: HasTable) -> frozenset[str]:
    """Return the names of columns a guild moderator may edit, per their `doc` marker."""
    return frozenset(
        column.name
        for column in model.__table__.columns
        if column.doc and WEB_EDITABLE in column.doc
    )


def web_editable_docs(model: HasTable) -> dict[str, str]:
    """Map each web-editable column name to its help text (its `doc` minus the marker)."""
    return {
        column.name: column.doc.replace(WEB_EDITABLE, "").strip()
        for column in model.__table__.columns
        if column.doc and WEB_EDITABLE in column.doc
    }


__all__ = [
    "MAX_RULES_LENGTH",
    "WEB_EDITABLE",
    "Alert",
    "Base",
    "Block",
    "Channel",
    "Game",
    "GameStatus",
    "Guild",
    "GuildAward",
    "GuildMember",
    "Play",
    "Post",
    "Queue",
    "Token",
    "User",
    "UserAward",
    "Verify",
    "Watch",
    "create_all",
    "generate_pin",
    "import_models",
    "literalquery",
    "now",
    "reverse_all",
    "web_editable",
    "web_editable_columns",
    "web_editable_docs",
]
