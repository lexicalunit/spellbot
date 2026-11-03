# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging

from ddtrace.trace import tracer

from spellbot import services
from spellbot.i18n import t, user_locale
from spellbot.integrations.playgroup_live import find_playgroup_user
from spellbot.operations import safe_followup_channel

from .base_action import BaseAction

logger = logging.getLogger(__name__)


class PlaygroupAction(BaseAction):
    @tracer.wrap()
    async def link(self) -> None:
        """Link the user's Discord account to their Playgroup Live account."""
        assert self.user_data is not None
        locale = user_locale(self.interaction)
        if self.user_data.playgroup_user_id is not None:
            message = t("playgroup.already_linked", locale=locale)
        else:
            playgroup_user_id, username = await find_playgroup_user(self.interaction.user.id)
            if playgroup_user_id is None:
                message = t("playgroup.not_found", locale=locale)
            else:
                await services.users.set_playgroup_user_id(
                    self.interaction.user.id,
                    playgroup_user_id,
                )
                message = t("playgroup.linked", locale=locale, username=username)
        await safe_followup_channel(self.interaction, message, ephemeral=True)
