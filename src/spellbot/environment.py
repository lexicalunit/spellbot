from __future__ import annotations

import sys
from os import getenv


def running_in_pytest() -> bool:  # pragma: no cover
    return bool(getenv("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules
