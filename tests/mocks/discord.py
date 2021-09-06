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

    def __get_user(self, id):
        for user in self.users:
            if user.id == id:
                return user

    def get_user(self, id):
        return self.__get_user(id)

    async def fetch_user(self, id):
        return self.__get_user(id)

    def __get_channel(self, id):
        for channel in self.channels:
            if channel.id == id:
                return channel

    def get_channel(self, id):
        return self.__get_channel(id)

    async def fetch_channel(self, id):
        return self.__get_channel(id)

    def __get_guild(self, id):
        for guild in self.guilds:
            if guild.id == id:
                return guild

    def get_guild(self, id):
        return self.__get_guild(id)

    async def fetch_guild(self, id):
        return self.__get_guild(id)


def make_client(*args, **kwargs) -> discord.Client:
    return cast(discord.Client, MockClient(*args, **kwargs))
