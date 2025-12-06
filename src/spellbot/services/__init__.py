from __future__ import annotations

from .apps import AppsService
from .awards import AwardsService, NewAward
from .channels import ChannelsService
from .games import GamesService
from .guilds import GuildsService
from .notifications import NotificationData, NotificationsService
from .patreon import PatreonService
from .plays import PlaysService
from .users import UsersService
from .verifies import VerifiesService
from .watches import WatchesService


class ServicesRegistry:
    def __init__(self) -> None:
        self.apps = AppsService()
        self.awards = AwardsService()
        self.channels = ChannelsService()
        self.games = GamesService()
        self.guilds = GuildsService()
        self.notifications = NotificationsService()
        self.patreon = PatreonService()
        self.plays = PlaysService()
        self.users = UsersService()
        self.verifies = VerifiesService()
        self.watches = WatchesService()


__all__ = [
    "AppsService",
    "AwardsService",
    "ChannelsService",
    "GamesService",
    "GuildsService",
    "NewAward",
    "NotificationData",
    "NotificationsService",
    "PatreonService",
    "PlaysService",
    "ServicesRegistry",
    "UsersService",
    "VerifiesService",
    "WatchesService",
]
