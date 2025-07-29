from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.models import Channel, Guild
from spellbot.services import ChannelsService
from tests.factories import ChannelFactory

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceChannels:
    async def test_channels_upsert(self, guild: Guild) -> None:
        channels = ChannelsService()
        discord_channel = MagicMock()
        discord_channel.id = 201
        discord_channel.name = "channel-name"
        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_channel.guild = discord_guild
        await channels.upsert(discord_channel)

        DatabaseSession.expire_all()
        channel = DatabaseSession.get(Channel, discord_channel.id)
        assert channel
        assert channel.xid == discord_channel.id
        assert channel.name == "channel-name"

        discord_channel.name = "new-name"
        await channels.upsert(discord_channel)

        DatabaseSession.expire_all()
        channel = DatabaseSession.get(Channel, discord_channel.id)
        assert channel
        assert channel.xid == discord_channel.id
        assert channel.name == "new-name"

    async def test_channels_select(self, guild: Guild) -> None:
        channels = ChannelsService()
        assert not await channels.select(404)

        ChannelFactory.create(guild=guild, xid=404)
        assert await channels.select(404)

    async def test_channels_current_default_seats(self, channel: Channel) -> None:
        channels = ChannelsService()
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["default_seats"] == channel.default_seats

    async def test_channels_set_default_seats(self, channel: Channel) -> None:
        channels = ChannelsService()
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["default_seats"] != 2

        await channels.set_default_seats(channel.xid, 2)
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["default_seats"] == 2

    async def test_channels_should_auto_verify(self, guild: Guild) -> None:
        channel = ChannelFactory.create(guild=guild, auto_verify=True)

        channels = ChannelsService()
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["auto_verify"]

    async def test_channels_verified_only(self, guild: Guild) -> None:
        channel = ChannelFactory.create(guild=guild, verified_only=True)

        channels = ChannelsService()
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["verified_only"]

    async def test_channels_unverified_only(self, guild: Guild) -> None:
        channel = ChannelFactory.create(guild=guild, unverified_only=True)

        channels = ChannelsService()
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["unverified_only"]

    async def test_channels_set_auto_verify(self, guild: Guild) -> None:
        channel = ChannelFactory.create(guild=guild, auto_verify=False)

        channels = ChannelsService()
        await channels.set_auto_verify(channel.xid, True)
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["auto_verify"]

    async def test_channels_set_verified_only(self, guild: Guild) -> None:
        channel = ChannelFactory.create(guild=guild, verified_only=False)

        channels = ChannelsService()
        await channels.set_verified_only(channel.xid, True)
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["verified_only"]

    async def test_channels_set_unverified_only(self, guild: Guild) -> None:
        channel = ChannelFactory.create(guild=guild, unverified_only=False)

        channels = ChannelsService()
        await channels.set_unverified_only(channel.xid, True)
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["unverified_only"]

    async def test_channels_set_motd(self, guild: Guild) -> None:
        channels = ChannelsService()

        channel = ChannelFactory.create(guild=guild, motd="whatever")
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["motd"] == "whatever"

        await channels.set_motd(channel.xid, "something else")
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["motd"] == "something else"

    async def test_channels_set_delete_expired(self, guild: Guild) -> None:
        channels = ChannelsService()

        channel = ChannelFactory.create(guild=guild, delete_expired=False)
        data = await channels.select(channel.xid)
        assert data is not None
        assert not data["delete_expired"]

        await channels.set_delete_expired(channel.xid, True)
        data = await channels.select(channel.xid)
        assert data is not None
        assert data["delete_expired"]
