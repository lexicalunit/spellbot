from typing import cast
from unittest.mock import MagicMock

import discord


class MockClient:
    def __init__(
        self,
        *,
        user=MagicMock(),
        loop=MagicMock(),
        channels=None,
        guilds=None,
        users=None,
        categories=None,
    ):
        self.user = user
        self.loop = loop
        self.channels = channels or []
        self.guilds = guilds or []
        self.users = users or []
        self.categoies = categories or []

    def __get_user(self, xid):
        for user in self.users:
            if user.id == xid:
                return user

    def get_user(self, xid):
        return self.__get_user(xid)

    async def fetch_user(self, xid):
        return self.__get_user(xid)

    def __get_channel(self, xid):
        for channel in self.channels:
            if channel.id == xid:
                return channel

    def get_channel(self, xid):
        return self.__get_channel(xid)

    async def fetch_channel(self, xid):
        return self.__get_channel(xid)

    def __get_guild(self, xid):
        for guild in self.guilds:
            if guild.id == xid:
                return guild

    def get_guild(self, xid):
        return self.__get_guild(xid)

    async def fetch_guild(self, xid):
        return self.__get_guild(xid)


def make_client(*args, **kwargs) -> discord.Client:
    return cast(discord.Client, MockClient(*args, **kwargs))
