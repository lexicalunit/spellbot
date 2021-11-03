from tests.factories.guild import GuildFactory
from tests.factories.user import UserFactory
from tests.factories.watch import WatchFactory


class TestModelWatch:
    def test_watch(self):
        guild = GuildFactory.create()
        user = UserFactory.create()
        watch = WatchFactory.create(note="note", user_xid=user.xid, guild_xid=guild.xid)

        assert watch.to_dict() == {
            "guild_xid": watch.guild_xid,
            "user_xid": watch.user_xid,
            "note": watch.note,
        }
