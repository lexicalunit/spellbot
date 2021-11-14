from discord.ext.commands.errors import CheckFailure


class SpellBotError(CheckFailure):
    ...


class AdminOnlyError(SpellBotError):
    def __init__(self, message=None):
        super().__init__(message or "This command is only available to SpellBot admins.")


class UserBannedError(SpellBotError):
    def __init__(self, message=None):
        super().__init__(message or "This user has been banned from using SpellBot.")


class UserVerifiedError(SpellBotError):
    def __init__(self, message=None):
        super().__init__(message or "Verified user message in a unverified only channel.")


class UserUnverifiedError(SpellBotError):
    def __init__(self, message=None):
        super().__init__(message or "Unverified user message in a verified only channel.")
