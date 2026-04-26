from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.models import Guild, GuildAward
from spellbot.services import GuildsService
from tests.factories import ChannelFactory, GuildAwardFactory, GuildFactory

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

    async def test_guilds_get(self) -> None:
        guilds = GuildsService()
        assert not await guilds.get(404)

        GuildFactory.create(xid=404)

        guild_data = await guilds.get(404)
        assert guild_data is not None
        assert guild_data.xid == 404

    async def test_guilds_set_motd(self) -> None:
        guild = GuildFactory.create()
        guilds = GuildsService()
        guild_data = await guilds.get(guild.xid)
        assert guild_data is not None

        message_of_the_day = "message of the day"
        updated_guild_data = await guilds.set_motd(guild_data, message_of_the_day)

        assert updated_guild_data.motd == message_of_the_day
        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, guild.xid)
        assert guild
        assert guild.motd == message_of_the_day

    async def test_guilds_set_banned(self) -> None:
        guilds = GuildsService()
        guild = GuildFactory.create()

        await guilds.set_banned(guild.xid, banned=True)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, guild.xid)
        assert guild
        assert guild.banned

    async def test_guilds_toggle_show_links(self) -> None:
        guild = GuildFactory.create(xid=101, show_links=False)
        guilds = GuildsService()
        guild_data = await guilds.get(101)
        assert guild_data is not None
        assert not guild_data.show_links

        guild_data = await guilds.toggle_show_links(guild_data)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert guild.show_links
        assert guild_data.show_links

        guild_data = await guilds.toggle_show_links(guild_data)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert not guild.show_links
        assert not guild_data.show_links

    async def test_guilds_toggle_voice_create(self) -> None:
        guild = GuildFactory.create(xid=101, voice_create=False)
        guilds = GuildsService()
        guild_data = await guilds.get(101)
        assert guild_data is not None
        assert not guild_data.voice_create

        guild_data = await guilds.toggle_voice_create(guild_data)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert guild.voice_create
        assert guild_data.voice_create

        guild_data = await guilds.toggle_voice_create(guild_data)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert not guild.voice_create
        assert not guild_data.voice_create

    async def test_guilds_voiced(self) -> None:
        guilds = GuildsService()
        assert await guilds.voiced() == []

        guild1 = GuildFactory.create(voice_create=True)
        GuildFactory.create()
        guild3 = GuildFactory.create(voice_create=True)

        assert set(await guilds.voiced()) == {guild1.xid, guild3.xid}

    async def test_guilds_award_add(self) -> None:
        guilds = GuildsService()
        discord_guild = MagicMock()
        discord_guild.id = 101
        discord_guild.name = "guild-name"
        await guilds.upsert(discord_guild)
        await guilds.award_add(
            guild_xid=discord_guild.id,
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
        assert await guilds.has_award_with_count(guild.xid, award1.count)
        assert await guilds.has_award_with_count(guild.xid, award2.count)
        assert not await guilds.has_award_with_count(guild.xid, 30)

    async def test_guilds_setup_mythic_track(self) -> None:
        guild = GuildFactory.create(xid=101, enable_mythic_track=False)
        guilds = GuildsService()
        guild_data = await guilds.get(guild.xid)
        assert guild_data is not None
        assert not guild_data.enable_mythic_track

        guild_data = await guilds.setup_mythic_track(guild_data)

        assert guild_data.enable_mythic_track
        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert guild.enable_mythic_track

    async def test_guilds_toggle_use_max_bitrate(self) -> None:
        guild = GuildFactory.create(xid=101, use_max_bitrate=False)
        guilds = GuildsService()
        guild_data = await guilds.get(101)
        assert guild_data is not None
        assert not guild_data.use_max_bitrate

        guild_data = await guilds.toggle_use_max_bitrate(guild_data)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert guild.use_max_bitrate
        assert guild_data.use_max_bitrate

        guild_data = await guilds.toggle_use_max_bitrate(guild_data)

        DatabaseSession.expire_all()
        guild = DatabaseSession.get(Guild, 101)
        assert guild
        assert not guild.use_max_bitrate
        assert not guild_data.use_max_bitrate

    async def test_guilds_voice_category_prefixes(self) -> None:

        guild = GuildFactory.create(xid=101)
        ChannelFactory.create(guild=guild, voice_category="Voice Channels")
        ChannelFactory.create(guild=guild, voice_category="Voice Channels")
        ChannelFactory.create(guild=guild, voice_category="Other Category")

        guilds = GuildsService()
        prefixes = await guilds.voice_category_prefixes(guild.xid)

        assert set(prefixes) == {"Voice Channels", "Other Category"}
