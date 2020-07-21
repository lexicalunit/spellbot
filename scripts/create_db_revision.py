#!/usr/bin/env python3

import sys
from os.path import dirname, realpath
from pathlib import Path

import alembic  # type: ignore
import alembic.command  # type: ignore
import alembic.config  # type: ignore

SRC_ROOT = Path(dirname(realpath(__file__))).parent
ASSETS_DIR = SRC_ROOT / "src" / "spellbot" / "assets"
ALEMBIC_INI = ASSETS_DIR / "alembic.ini"
VERSIONS_DIR = SRC_ROOT / "src" / "spellbot" / "versions"

url = sys.argv[1]
message = sys.argv[2]

config = alembic.config.Config(str(ALEMBIC_INI))
config.set_main_option("script_location", str(VERSIONS_DIR))
config.set_main_option("sqlalchemy.url", url)
alembic.command.revision(config, message=message, autogenerate=True)
