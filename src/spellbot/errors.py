from discord.ext.commands.errors import CheckFailure


class SpellbotAdminOnly(CheckFailure):
    def __init__(self, message=None):
        super().__init__(message or "This command is only available to SpellBot admins.")


class UserBannedError(CheckFailure):
    def __init__(self, message=None):
        super().__init__(message or "This user has been banned from using SpellBot.")
