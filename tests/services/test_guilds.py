from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.models import Guild, GuildAward
from spellbot.services import GuildsService
from tests.factories import GuildAwardFactory, GuildFactory

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceGuilds:
    async def test_guilds_upsert(self) -> None:
        discord_guild = MagicMock()
        discord_guild.id = 101
        discord_guild.name = "guild-name"
        guilds = GuildsService()
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, discord_guild.id)
        assert guild
        assert guild.xid == discord_guild.id
        assert guild.name == "guild-name"

        discord_guild.name = "new-name"
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, discord_guild.id)
        assert guild
        assert guild.xid == discord_guild.id
        assert guild.name == "new-name"

    async def test_guilds_select(self) -> None:
        guilds = GuildsService()
        assert not await guilds.select(404)

        GuildFactory.create(xid=404)

        assert await guilds.select(404)

    async def test_guilds_should_voice_create(self) -> None:
        guild1 = GuildFactory.create()
        guild2 = GuildFactory.create(voice_create=True)

        guilds = GuildsService()
        await guilds.select(guild1.xid)
        assert not await guilds.should_voice_create()
        await guilds.select(guild2.xid)
        assert await guilds.should_voice_create()

    async def test_guilds_get_use_max_bitrate(self) -> None:
        guild1 = GuildFactory.create()
        guild2 = GuildFactory.create(use_max_bitrate=True)

        guilds = GuildsService()
        await guilds.select(guild1.xid)
        assert not await guilds.get_use_max_bitrate()
        await guilds.select(guild2.xid)
        assert await guilds.get_use_max_bitrate()

    async def test_guilds_set_motd(self) -> None:
        guilds = GuildsService()
        assert not await guilds.select(101)

        guild = GuildFactory.create()

        await guilds.select(guild.xid)
        message_of_the_day = "message of the day"
        await guilds.set_motd(message_of_the_day)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, guild.xid)
        assert guild
        assert guild.motd == message_of_the_day

    async def test_guilds_set_banned(self) -> None:
        guilds = GuildsService()
        guild = GuildFactory.create()

        await guilds.set_banned(True, guild.xid)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, guild.xid)
        assert guild
        assert guild.banned

    async def test_guilds_toggle_show_links(self) -> None:
        guilds = GuildsService()
        assert not await guilds.select(101)

        guild = GuildFactory.create(xid=101)

        await guilds.select(101)
        await guilds.toggle_show_links()

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert guild.show_links
        DatabaseSession.expire_all()

        await guilds.select(101)
        await guilds.toggle_show_links()
        DatabaseSession.expire_all()

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert not guild.show_links

    async def test_guilds_toggle_voice_create(self) -> None:
        guilds = GuildsService()
        assert not await guilds.select(101)

        guild = GuildFactory.create(xid=101)

        guilds = GuildsService()
        await guilds.select(101)
        await guilds.toggle_voice_create()

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert guild.voice_create

        await guilds.select(101)
        await guilds.toggle_voice_create()

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert not guild.voice_create

    async def test_guilds_current_name(self) -> None:
        guild = GuildFactory.create(xid=101)

        guilds = GuildsService()
        await guilds.select(101)
        assert await guilds.current_name() == guild.name

    async def test_guilds_voiced(self) -> None:
        guilds = GuildsService()
        assert await guilds.voiced() == []

        guild1 = GuildFactory.create(voice_create=True)
        GuildFactory.create()
        guild3 = GuildFactory.create(voice_create=True)

        assert set(await guilds.voiced()) == {guild1.xid, guild3.xid}

    async def test_guilds_to_dict(self) -> None:
        guild = GuildFactory.create(xid=101)

        guilds = GuildsService()
        await guilds.select(101)
        service_dict = await guilds.to_dict()
        assert guild.to_dict() == service_dict

    async def test_guilds_award_add(self) -> None:
        guilds = GuildsService()
        discord_guild = MagicMock()
        discord_guild.id = 101
        discord_guild.name = "guild-name"
        await guilds.upsert(discord_guild)
        await guilds.award_add(
            count=5,
            role="a-role",
            message="a-message",
        )

        award = (
            DatabaseSession.query(GuildAward)
            .filter(
                GuildAward.count == 5,
            )
            .one_or_none()
        )
        assert award
        assert award.role == "a-role"
        assert award.message == "a-message"
        assert award.guild_xid == discord_guild.id

    async def test_guilds_award_delete(self, guild: Guild) -> None:
        award1 = GuildAwardFactory.create(guild=guild)
        award2 = GuildAwardFactory.create(guild=guild)

        guilds = GuildsService()
        await guilds.select(guild.xid)
        award1_id = award1.id
        await guilds.award_delete(award1.id)
        await guilds.award_delete(404)

        DatabaseSession.expire_all()
        assert not DatabaseSession.get(GuildAward, award1_id)
        assert DatabaseSession.get(GuildAward, award2.id)

    async def test_guilds_has_award_with_count(self, guild: Guild) -> None:
        award1 = GuildAwardFactory.create(guild=guild, count=10)
        award2 = GuildAwardFactory.create(guild=guild, count=20)

        guilds = GuildsService()
        await guilds.select(guild.xid)
        assert await guilds.has_award_with_count(award1.count)
        assert await guilds.has_award_with_count(award2.count)
        assert not await guilds.has_award_with_count(30)

    async def test_guilds_setup_mythic_track(self) -> None:
        guild = GuildFactory.create(xid=101, enable_mythic_track=False)
        guilds = GuildsService()
        await guilds.select(guild.xid)

        setting = await guilds.setup_mythic_track()

        assert setting
