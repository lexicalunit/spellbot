from __future__ import annotations

from importlib import import_module
from inspect import getmembers, isclass
from pathlib import Path
from pkgutil import iter_modules


def import_models() -> None:  # pragma: no cover
    package_dir = Path(__file__).resolve().parent
    for info in iter_modules([str(package_dir)]):
        module = import_module(f"{__name__}.{info.name}")
        for name, _object in getmembers(module, isclass):
            if isclass(_object) and issubclass(_object, Base) and name not in globals():
                globals()[name] = _object


from .base import Base, create_all, literalquery, now, reverse_all  # noqa: I001,E402

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

__all__ = [
    "MAX_RULES_LENGTH",
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
]
