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

from .award import GuildAward, UserAward, GuildAwardDict, UserAwardDict  # noqa: E402
from .block import Block, BlockDict  # noqa: E402
from .channel import Channel, ChannelDict  # noqa: E402
from .game import Game, GameStatus, GameDict  # noqa: E402
from .guild import Guild, GuildDict  # noqa: E402
from .mirror import Mirror, MirrorDict  # noqa: E402
from .play import Play, PlayDict  # noqa: E402
from .post import Post, PostDict  # noqa: E402
from .queue import Queue, QueueDict  # noqa: E402
from .user import User, UserDict  # noqa: E402
from .verify import Verify, VerifyDict  # noqa: E402
from .watch import Watch, WatchDict  # noqa: E402

__all__ = [
    "Base",
    "Block",
    "BlockDict",
    "Channel",
    "ChannelDict",
    "create_all",
    "Game",
    "GameDict",
    "GameDict",
    "GameStatus",
    "Guild",
    "GuildAward",
    "GuildAwardDict",
    "GuildDict",
    "import_models",
    "literalquery",
    "Mirror",
    "MirrorDict",
    "now",
    "Play",
    "PlayDict",
    "Post",
    "PostDict",
    "Queue",
    "QueueDict",
    "reverse_all",
    "User",
    "UserAward",
    "UserAwardDict",
    "UserDict",
    "Verify",
    "VerifyDict",
    "Watch",
    "WatchDict",
]
