from spellbot.database import DatabaseSession
from spellbot.models.guild import Guild
from spellbot.models.user import User
from spellbot.models.watch import Watch


class TestModelWatch:
    def test_watch(self):
        guild = Guild(xid=101, name="guild-name")
        user = User(xid=201, name="user-name")
        watch = Watch(note="note", user_xid=user.xid, guild_xid=guild.xid)
        DatabaseSession.add_all([guild, user, watch])
        DatabaseSession.commit()

        assert watch.to_dict() == {
            "guild_xid": watch.guild_xid,
            "user_xid": watch.user_xid,
            "note": watch.note,
        }
