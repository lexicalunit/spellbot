from spellbot.web.builder import humanize


class TestWebFilters:
    async def test_humanize_happy_path(self):
        s = humanize(1638137981, 480, "America/Los_Angeles")
        assert s == "January 19, 1970 at 3:02:17 PM PST"

    async def test_humanize_bogus_timezone(self):
        s = humanize(1638137981, 480, "BOGUS")
        assert s == "January 19, 1970 at 3:02:17 PM UTC"
