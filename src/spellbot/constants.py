from datetime import datetime

ADMIN_ROLE = "SpellBot Admin"
CREATE_ENDPOINT = "https://us-central1-magic-night-30324.cloudfunctions.net/createGame"
THUMB_URL = (
    "https://raw.githubusercontent.com/lexicalunit/spellbot/master/spellbot.png"
    f"?{datetime.today().strftime('%Y-%m-%d')}"  # workaround over-eager caching
)
DEFAULT_GAME_SIZE = 4
INVITE_LINK = (
    "https://discordapp.com/api/oauth2/authorize"
    "?client_id=725510263251402832&permissions=92224&scope=bot"
)
VOTE_LINK = "https://top.gg/bot/725510263251402832/vote"
