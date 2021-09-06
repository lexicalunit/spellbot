import logging
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules

from discord.ext import commands
from discord.ext.commands import Bot

logger = logging.getLogger(__name__)
cog_module_names = set()

# iterate through the modules in the current package
package_dir = Path(__file__).resolve().parent
for info in iter_modules([str(package_dir)]):

    # import the module and iterate through its attributes
    module = import_module(f"{__name__}.{info.name}")
    for attribute_name in dir(module):  # pragma: no cover
        attribute = getattr(module, attribute_name)

        # Check if there's any cogs in this module
        if isclass(attribute) and issubclass(attribute, commands.Cog):
            cog_module_names.add(module.__name__)
            break


def load_all_cogs(bot: Bot) -> Bot:
    for module_name in cog_module_names:
        logger.info("loading cog module %s into bot...", module_name)
        bot.load_extension(module_name)
    return bot
