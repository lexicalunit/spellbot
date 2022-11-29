import logging
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules

from discord.ext import commands
from discord.ext.commands import AutoShardedBot

from .about_cog import AboutCog
from .admin_cog import AdminCog
from .block_cog import BlockCog
from .config_cog import ConfigCog
from .events_cog import EventsCog
from .leave_cog import LeaveGameCog
from .lfg_cog import LookingForGameCog
from .owner_cog import OwnerCog
from .score_cog import ScoreCog
from .sync_cog import SyncCog
from .tasks_cog import TasksCog
from .verify_cog import VerifyCog
from .watch_cog import WatchCog

logger = logging.getLogger(__name__)

# Only exported cogs will be loaded into the bot at runtime.
__all__ = [
    "AboutCog",
    "AdminCog",
    "BlockCog",
    "ConfigCog",
    "EventsCog",
    "LeaveGameCog",
    "LookingForGameCog",
    "OwnerCog",
    "ScoreCog",
    "SyncCog",
    "TasksCog",
    "VerifyCog",
    "WatchCog",
]


async def load_all_cogs(bot: AutoShardedBot) -> AutoShardedBot:
    # iterate through the modules in the current package
    package_dir = Path(__file__).resolve().parent
    for info in iter_modules([str(package_dir)]):

        # import the module and iterate through its attributes
        module = import_module(f"{__name__}.{info.name}")
        for attribute_name in dir(module):  # pragma: no cover
            attribute = getattr(module, attribute_name)

            # Only load cogs in this module if they're exported
            if (
                isclass(attribute)
                and issubclass(attribute, commands.Cog)
                and attribute.__name__ in __all__
            ):
                if module.__name__ in bot.extensions:
                    logger.info("reloading extension %s...", module.__name__)
                    await bot.reload_extension(module.__name__)
                else:
                    logger.info("loading extension %s...", module.__name__)
                    await bot.load_extension(module.__name__)
                break
    return bot
