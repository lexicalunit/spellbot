from __future__ import annotations

from importlib import import_module
from inspect import getmembers, isclass
from pathlib import Path
from pkgutil import iter_modules


def import_models():  # pragma: no cover
    package_dir = Path(__file__).resolve().parent
    for info in iter_modules([str(package_dir)]):
        module = import_module(f"{__name__}.{info.name}")
        for name, _object in getmembers(module, isclass):
            if isclass(_object) and issubclass(_object, Base):
                if name not in globals():
                    globals()[name] = _object


from .base import Base, create_all, literalquery, now, reverse_all  # isort:skip

from .award import GuildAward, UserAward
from .block import Block
from .channel import Channel
from .config import Config
from .game import Game, GameFormat, GameStatus
from .guild import Guild
from .play import Play
from .user import User
from .verify import Verify
from .watch import Watch

__all__ = [
    "Base",
    "Block",
    "Channel",
    "Config",
    "create_all",
    "Game",
    "GameFormat",
    "GameStatus",
    "Guild",
    "GuildAward",
    "import_models",
    "literalquery",
    "now",
    "Play",
    "reverse_all",
    "User",
    "UserAward",
    "Verify",
    "Watch",
]
