<img align="right" width="200" src="https://raw.githubusercontent.com/lexicalunit/spellbot/master/spellbot.png" />

# SpellBot

[![build][build-badge]][build]
[![pypi][pypi-badge]][pypi]
[![codecov][codecov-badge]][codecov]
[![python][python-badge]][python]
[![black][black-badge]][black]
[![mit][mit-badge]][mit]

The Discord bot for [SpellTable][spelltable].

[![add-bot][add-bot-button]][add-bot]

[![ko-fi][kofi-button]][ko-fi]

## 🤖 Using SpellBot

Once you've connected the bot to your server, you can interact with it over
Discord via the following commands in any of the authorized channels. **Keep in
mind that sometimes SpellBot will respond to you via Direct Message to avoid
being too spammy in text channels.**

- `!help`: Provides detailed help about all of the following commands.
- `!about`: Get information about SpellBot and its creators.

> **Note:** To use the
> [commands for event runners](#%EF%B8%8F-commands-for-event-runners)
> and [commands for admins](#-commands-for-admins), you will need to
> [create a role on your server][create-role] called `SpellBot Admin`
> (capitalization matters). Only users with that role will be able to use those
> commands.

### ✋ Commands for Players

Just looking to play some games of Magic? These commands are for you!

- `!lfg`: Sign up to play Magic: The Gathering!
- `!join`: Look for a game to join, but don't create a new one.
- `!leave`: Leave any games that you've signed up for.

When you run the `!lfg` command, SpellBot will post a message for sign ups.

![lfg][lfg]

Other users can react to it with the ➕ emoji to be added to the game. When the
game is ready, SpellBot will update the message with your SpellTable details.

![ready][ready]

Users can also use the ➖ emoji reaction to leave the game.

### 🎟️ Commands for Event Runners

These commands are intended to be run by SpellBot Admins and help facilitate
online events.

- `!game`: Directly create games for the mentioned users.
- `!queue`: Enter a player into an on-demand queue.
- `!event`: Create a bunch of games all at once based on some uploaded data.
- `!begin`: Start an event that you previously created with `!event`.
- `!export`: Export historical game data for your server.

### 👑 Commands for Admins

These commands will help you configure SpellBot for your server.

- `!spellbot`: This command allows admins to configure SpellBot for their
               server. It supports the following subcommands:
  - `config`: Just show the current configuration for this server.
  - `channels`: Set the channels SpellBot is allowed to operate within.
  - `prefix`: Set the command prefix for SpellBot in text channels.
  - `expire`: Set how many minutes before games are expired due to inactivity.

### 🛋️ Ergonomics

SpellBot will always try and assume useful defaults or try to do the right thing
when you give it a command. For example if you use the tag <code>~modern</code>
or other format names when creating a game, it will automatically assume the
correct number of players for you. Hopefully these features are intuitive and
helpful 🤞 — and if not, [please report bugs and request features][issues]
to your heart's content.

## 🙌 Support Me

I'm keeping SpellBot running using my own money but if you like the bot and want
to help me out, please consider donating to [my Ko-fi][ko-fi].

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
As well as your SpellTable API authorization token via `SPELLTABLE_AUTH`.

You can get [your bot token from Discord][discord-bot-docs]. Your bot will
need the following text permissions enabled:

- Send Messages
- Add Reactions

As for the SpellTable API authorization token, you'll have to talk to the
SpellTable developers. Come join us on the
[SpellTable Discord server][spelltable-discord].

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

[add-bot-button]:     https://user-images.githubusercontent.com/1903876/88951823-5d6c9a00-d24b-11ea-8523-d256ccbf4a3c.png
[add-bot]:            https://discordapp.com/api/oauth2/authorize?client_id=725510263251402832&permissions=92224&scope=bot
[black-badge]:        https://img.shields.io/badge/code%20style-black-000000.svg
[black]:              https://github.com/psf/black
[build-badge]:        https://github.com/lexicalunit/spellbot/workflows/build/badge.svg
[build]:              https://github.com/lexicalunit/spellbot/actions
[codecov-badge]:      https://codecov.io/gh/lexicalunit/spellbot/branch/master/graph/badge.svg
[codecov]:            https://codecov.io/gh/lexicalunit/spellbot
[contributors]:       https://github.com/lexicalunit/spellbot/graphs/contributors
[create-role]:        https://support.discord.com/hc/en-us/articles/206029707-How-do-I-set-up-Permissions-
[db-url]:             https://docs.sqlalchemy.org/en/latest/core/engines.html
[discord-bot-docs]:   https://discord.com/developers/docs/topics/oauth2#bots
[issues]:             https://github.com/lexicalunit/spellbot/issues
[ko-fi]:              https://ko-fi.com/Y8Y51VTHZ
[kofi-button]:        https://user-images.githubusercontent.com/1903876/88951826-5e053080-d24b-11ea-9a81-f1b5431a5d4b.png
[lexicalunit]:        http://github.com/lexicalunit
[lfg]:                https://user-images.githubusercontent.com/1903876/88854660-7a02c680-d1a6-11ea-9f12-75b9cbb439b4.png
[mit-badge]:          https://img.shields.io/badge/License-MIT-yellow.svg
[mit]:                https://opensource.org/licenses/MIT
[pypi-badge]:         https://img.shields.io/pypi/v/spellbot
[pypi]:               https://pypi.org/project/spellbot/
[python-badge]:       https://img.shields.io/badge/python-3.7+-blue.svg
[python]:             https://www.python.org/
[ready]:              https://user-images.githubusercontent.com/1903876/88854658-796a3000-d1a6-11ea-93b6-63dccae5d637.png
[spelltable-discord]: https://discord.gg/zXzgqMN
[spelltable]:         https://www.spelltable.com/
