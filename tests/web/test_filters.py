from __future__ import annotations

import pytest

from spellbot.web import humanize


@pytest.mark.asyncio
class TestWebFilters:
    async def test_humanize_happy_path(self) -> None:
        s = humanize(1638137981, 480, "America/Los_Angeles")
        assert s == "January 19, 1970, 3:02:17\u202fPM PST"

    async def test_humanize_bogus_timezone(self) -> None:
        s = humanize(1638137981, 480, "BOGUS")
        assert s == "January 19, 1970, 3:02:17\u202fPM UTC"
