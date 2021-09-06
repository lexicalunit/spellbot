#!/usr/bin/env python3

import sys
from os.path import dirname, realpath
from pathlib import Path

import alembic
import alembic.command
import alembic.config

SRC_ROOT = Path(dirname(realpath(__file__))).parent
SPELLBOT_DIR = SRC_ROOT / "src" / "spellbot"
MIGRATIONS_DIR = SPELLBOT_DIR / "migrations"
ALEMBIC_INI = MIGRATIONS_DIR / "alembic.ini"

url = sys.argv[1]
message = sys.argv[2]

config = alembic.config.Config(str(ALEMBIC_INI))
config.set_main_option("script_location", str(MIGRATIONS_DIR))
config.set_main_option("sqlalchemy.url", url)
alembic.command.revision(config, message=message, autogenerate=True)
