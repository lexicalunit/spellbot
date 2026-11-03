# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spellbot.data.channel_data import ChannelData


@dataclass(frozen=True)
class GameCriteria:
    """
    What a game is for. A player looking for a game only joins one that matches all of it.

    `war_title` is display only: matching uses `war_id`.
    """

    seats: int
    format: int
    bracket: int
    service: int
    rules: str | None = None
    war_id: str | None = None
    war_title: str | None = None


@dataclass(frozen=True)
class ChannelModes:
    """Channel settings snapshotted onto each game when it is created."""

    blind: bool = False
    to_mode: bool = False
    competitive_mode: bool = False

    @classmethod
    def from_channel(cls, channel: ChannelData) -> ChannelModes:
        return cls(
            blind=bool(channel.blind_games),
            to_mode=bool(channel.to_mode),
            competitive_mode=bool(channel.competitive_mode),
        )
