# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Decoy-backed builders for discord.py objects, mirroring the `build_*` helpers in `tests.mocks`.

Unlike `MagicMock`, a decoy keeps the real discord.py type, so calls can be verified with full
type checking: `decoy.verify(await message.delete())`. Plain attributes are assigned directly;
read-only properties must be stubbed with `decoy.when(obj.prop).then_return(...)`.
Decoy never invents behavior, so anything the code under test reads that isn't set up here comes
back as a bare mock: stub it in the test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from decoy import matchers

from tests.mocks import OWNER_USER_ID

if TYPE_CHECKING:
    from decoy import Decoy


def guild(decoy: Decoy, offset: int = 1) -> discord.Guild:
    guild = decoy.mock(cls=discord.Guild)
    guild.id = 2000 + offset
    guild.name = f"guild-{guild.id}"
    guild.owner_id = OWNER_USER_ID
    guild.preferred_locale = discord.Locale.american_english
    decoy.when(guild.bitrate_limit).then_return(64000.0)
    return guild


def channel(decoy: Decoy, guild: discord.Guild, offset: int = 1) -> discord.TextChannel:
    channel = decoy.mock(cls=discord.TextChannel)
    channel.id = 3000 + offset
    channel.name = f"channel-{channel.id}"
    channel.guild = guild
    decoy.when(channel.type).then_return(discord.ChannelType.text)
    decoy.when(channel.permissions_for(matchers.IsA(discord.Member))).then_return(
        discord.Permissions(),
    )
    return channel


def member(decoy: Decoy, offset: int = 1) -> discord.Member:
    member = decoy.mock(cls=discord.Member)
    member.id = 1000 + offset
    decoy.when(member.display_name).then_return(f"user-{member.id}")
    decoy.when(member.mention).then_return(f"<@{member.id}>")
    decoy.when(member.roles).then_return([])
    return member


def message(
    decoy: Decoy,
    guild: discord.Guild,
    channel: discord.TextChannel,
    author: discord.Member,
    offset: int = 1,
) -> discord.Message:
    message = decoy.mock(cls=discord.Message)
    message.id = 4000 + offset
    message.content = "content"
    message.guild = guild
    message.channel = channel
    message.author = author
    return message
