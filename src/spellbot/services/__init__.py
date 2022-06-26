# pylint: disable=too-many-instance-attributes
from __future__ import annotations

from .awards import AwardsService, NewAward
from .channels import ChannelsService
from .configs import ConfigsService
from .games import GamesService
from .guilds import GuildsService
from .plays import PlaysService
from .users import UsersService
from .verifies import VerifiesService
from .watches import WatchesService


class ServicesRegistry:
    def __init__(self):
        self.awards = AwardsService()
        self.channels = ChannelsService()
        self.configs = ConfigsService()
        self.games = GamesService()
        self.guilds = GuildsService()
        self.plays = PlaysService()
        self.users = UsersService()
        self.verifies = VerifiesService()
        self.watches = WatchesService()


__all__ = [
    "AwardsService",
    "ChannelsService",
    "ConfigsService",
    "GamesService",
    "GuildsService",
    "NewAward",
    "PlaysService",
    "ServicesRegistry",
    "UsersService",
    "VerifiesService",
    "WatchesService",
]
