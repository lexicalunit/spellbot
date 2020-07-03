<img align="right" src="https://raw.githubusercontent.com/lexicalunit/spellbot/master/spellbot.png" />

# SpellBot

[![build][build-badge]][build]
[![pypi][pypi-badge]][pypi]
[![codecov][codecov-badge]][codecov]
[![python][python-badge]][python]
[![black][black-badge]][black]
[![mit][mit-badge]][mit]

A Discord bot for [SpellTable][spelltable].

[![add-bot][add-img]][add-bot]

[![ko-fi](https://www.ko-fi.com/img/githubbutton_sm.svg)][ko-fi]

## 🤖 Using SpellBot

Once you've connected the bot to your server, you can interact with it over
Discord via the following commands in any of the authorized channels.

- `!help`: Provides detailed help about all of the following commands.
- `!about`: Get information about SpellBot and its creators.

### ✋ Queueing

- `!queue`: Get in line to play some Magic: The Gathering!
- `!leave`: Get out of line; it's the opposite of `!queue`.
- `!status`: Show some details about the queues on your server.

### 👑 Administration

- `!spellbot`: Admin subcommands to configure SpellBot for your server.

**Subcommands:**

- `channels`: Set the channels SpellBot is allowed to operate within.
- `prefix`: Set the command prefix for SpellBot in text channels.

## 🙌 Support Me

I'm keeping SpellBot running using my own money but if you like the bot and want
to help me out, please consider donating to [my ko-fi][ko-fi].

## ❤️ Contributing

If you'd like to become a part of the SpellBot development community please
first know that we have a documented [code of conduct](CODE_OF_CONDUCT.md) and
then see our [documentation on how to contribute](CONTRIBUTING.md) for details
on how to get started.

## 🔧 Running SpellBot Yourself

First install `spellbot` using [`pip`](https://pip.pypa.io/en/stable/):

```shell
pip install spellbot
```

Provide your Discord bot token with the environment variable `SPELLBOT_TOKEN`.
As well as your SpellTable API authorization token via `SPELLTABLE_AUTH`. You
can get [your bot token from Discord][discord-bot-docs]. As for the SpellTable
API authorization token, you'll have to talk to the SpellTable developers.
You can join their Discord server by
[becoming a SpellTable patron][spelltable-patron].

By default SpellBot will use sqlite3 as its database. You can however choose to
use another database by providing a [SQLAlchemy Connection URL][db-url]. This
can be done via the `--database-url` command line option or the environment
variable `SPELLBOT_DB_URL`. Note that, at the time of this writing, SpellBot is
only tested against sqlite3 and PostgreSQL.

More usage help can be found by running `spellbot --help`.

## 🐳 Docker Support

You can also run SpellBot via docker. See
[our documentation on Docker Support](DOCKER.md) for help.

---

[MIT][mit] © [amy@lexicalunit][lexicalunit] et [al][contributors]

[add-bot]:            https://discordapp.com/api/oauth2/authorize?client_id=725510263251402832&permissions=247872&scope=bot
[add-img]:            https://user-images.githubusercontent.com/1903876/82262797-71745100-9916-11ea-8b65-b3f656115e4f.png
[black-badge]:        https://img.shields.io/badge/code%20style-black-000000.svg
[black]:              https://github.com/psf/black
[build-badge]:        https://github.com/lexicalunit/spellbot/workflows/build/badge.svg
[build]:              https://github.com/lexicalunit/spellbot/actions
[codecov-badge]:      https://codecov.io/gh/lexicalunit/spellbot/branch/master/graph/badge.svg
[codecov]:            https://codecov.io/gh/lexicalunit/spellbot
[contributors]:       https://github.com/lexicalunit/spellbot/graphs/contributors
[db-url]:             https://docs.sqlalchemy.org/en/latest/core/engines.html
[discord-bot-docs]:   https://discord.com/developers/docs/topics/oauth2#bots
[ko-fi]:              https://ko-fi.com/Y8Y51VTHZ
[lexicalunit]:        http://github.com/lexicalunit
[mit-badge]:          https://img.shields.io/badge/License-MIT-yellow.svg
[mit]:                https://opensource.org/licenses/MIT
[pypi-badge]:         https://img.shields.io/pypi/v/spellbot
[pypi]:               https://pypi.org/project/spellbot/
[python-badge]:       https://img.shields.io/badge/python-3.7+-blue.svg
[python]:             https://www.python.org/
[spelltable-patron]:  https://www.patreon.com/spelltable?fan_landing=true
[spelltable]:         https://www.spelltable.com/
