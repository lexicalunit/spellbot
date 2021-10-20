from unittest.mock import MagicMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.models.channel import Channel
from spellbot.services.channels import ChannelsService
from tests.factories.channel import ChannelFactory


@pytest.mark.asyncio
class TestServiceChannels:
    async def test_channels_upsert(self, guild):
        channels = ChannelsService()
        discord_channel = MagicMock()
        discord_channel.id = 201
        discord_channel.name = "channel-name"
        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_channel.guild = discord_guild
        await channels.upsert(discord_channel)

        DatabaseSession.expire_all()
        channel = DatabaseSession.query(Channel).get(discord_channel.id)
        assert channel and channel.xid == discord_channel.id
        assert channel.name == "channel-name"

        discord_channel.name = "new-name"
        await channels.upsert(discord_channel)

        DatabaseSession.expire_all()
        channel = DatabaseSession.query(Channel).get(discord_channel.id)
        assert channel and channel.xid == discord_channel.id
        assert channel.name == "new-name"

    async def test_channels_select(self, guild):
        channels = ChannelsService()
        assert not await channels.select(404)

        ChannelFactory.create(guild=guild, xid=404)
        DatabaseSession.commit()
        assert await channels.select(404)

    async def test_channels_current_default_seats(self, channel):
        channels = ChannelsService()
        await channels.select(channel.xid)
        assert await channels.current_default_seats() == channel.default_seats

    async def test_channels_set_default_seats(self, channel):
        channels = ChannelsService()
        await channels.select(channel.xid)
        assert await channels.current_default_seats() != 2
        await channels.set_default_seats(2)
        assert await channels.current_default_seats() == 2

    async def test_channels_should_auto_verify(self, guild):
        channel = ChannelFactory.create(guild=guild, auto_verify=True)
        DatabaseSession.commit()

        channels = ChannelsService()
        await channels.select(channel.xid)
        assert await channels.should_auto_verify()

    async def test_channels_verified_only(self, guild):
        channel = ChannelFactory.create(guild=guild, verified_only=True)
        DatabaseSession.commit()

        channels = ChannelsService()
        await channels.select(channel.xid)
        assert await channels.verified_only()

    async def test_channels_unverified_only(self, guild):
        channel = ChannelFactory.create(guild=guild, unverified_only=True)
        DatabaseSession.commit()

        channels = ChannelsService()
        await channels.select(channel.xid)
        assert await channels.unverified_only()

    async def test_channels_set_auto_verify(self, guild):
        channel = ChannelFactory.create(guild=guild, auto_verify=False)
        DatabaseSession.commit()

        channels = ChannelsService()
        await channels.select(channel.xid)
        await channels.set_auto_verify(True)
        assert await channels.should_auto_verify()

    async def test_channels_set_verified_only(self, guild):
        channel = ChannelFactory.create(guild=guild, verified_only=False)
        DatabaseSession.commit()

        channels = ChannelsService()
        await channels.select(channel.xid)
        await channels.set_verified_only(True)
        assert await channels.verified_only()

    async def test_channels_set_unverified_only(self, guild):
        channel = ChannelFactory.create(guild=guild, unverified_only=False)
        DatabaseSession.commit()

        channels = ChannelsService()
        await channels.select(channel.xid)
        await channels.set_unverified_only(True)
        assert await channels.unverified_only()
