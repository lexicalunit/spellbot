from datetime import datetime

ADMIN_ROLE = "SpellBot Admin"
CREATE_ENDPOINT = "https://us-central1-magic-night-30324.cloudfunctions.net/createGame"
THUMB_URL = (
    "https://raw.githubusercontent.com/lexicalunit/spellbot/master/spellbot.png"
    f"?{datetime.today().strftime('%Y-%m-%d')}"  # workaround over-eager caching
)
ICO_URL = (
    "https://raw.githubusercontent.com/lexicalunit/spellbot/master/spellbot-sm.png"
    f"?{datetime.today().strftime('%Y-%m-%d')}"  # workaround over-eager caching
)
DEFAULT_GAME_SIZE = 4
INVITE_LINK = (
    "https://discordapp.com/api/oauth2/authorize"
    "?client_id=725510263251402832&permissions=268528721&scope=bot"
)
VOTE_LINK = "https://top.gg/bot/725510263251402832/vote"

EMOJI_DROP_GAME = "🚫"
EMOJI_FAIL = "❌"
EMOJI_JOIN_GAME = "✋"
EMOJI_OK = "✅"

DEFAULT_PREFIX = "!"

VOICE_CATEGORY_PREFIX = "SpellBot Voice Channels"

VOICE_INVITE_EXPIRE_TIME_S = 14400  # 4 hours, make this configurable?
CLEAN_S = 7  # seconds before temporary messages by the bot get cleaned up, configurable?
REALLY_OLD_GAMES_HOURS = 5  # hours passed before game is considered really old
BATCH_LIMIT = 20  # cleanup voice channels in batches
