from __future__ import annotations

from typing import Optional

from discord.app_commands import AppCommandError


class SpellBotError(AppCommandError):
    ...


class AdminOnlyError(SpellBotError):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "This command is only available to SpellBot admins.")


class GuildOnlyError(SpellBotError):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "This command is only available within a guild.")


class UserBannedError(SpellBotError):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "This user has been banned from using SpellBot.")


class UserVerifiedError(SpellBotError):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "Verified user message in a unverified only channel.")


class UserUnverifiedError(SpellBotError):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "Unverified user message in a verified only channel.")
