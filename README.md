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

## 📱 Using SpellBot

Once you've connected the bot to your server, you can interact with it over
Discord via the following commands in any of the authorized channels.

- `!about`: Get information about SpellBot
- `!help`: Provides detailed help about all of the following commands
- `!hello`: Says hello

## WIP: MVP

- Allow users to queue, when there's enough people in the queue create a game for them

## WIP: Commands

### Queue

In a text channel or as a DM to the bot:

```text
!queue <format> [power level]
```

- Verifies that you're not in a queue yet
- Sends a DM to you indicating that you're in the queue
- When matchmaking is complete:
  - Creates a SpellTable link
  - DMs everyone in the match the link

### Status

As a DM to the bot:

```text
!status
```

- Gives you some information on your place in the queue
- Possibly give you some status on your history of games and win/lose

### Leaving

As a DM to the bot:

```text
!leave
```

- Removes you from the queue that you're in if you're in one

### Reporting

In a text channel:

```text
!report win @username[, @username, @username, ...]
!report draw @username[, @username, @username, ...]
```

- Automatically know what game based on the last game in which that user was a member of
- Indicates that @username is the winner of their match
- Potentially there could be multiple winners or draws
- Allow for mistakes, user's should be able to run report multiple times
- At some point after the first report, reporting needs be finalized
- Do we need a `!report loss` command for any reason?

### Moderation

As a DM to the bot by an authorized user:

```text
!ban @username <reason> [minutes]
```

- Block the user from being able to use the bot (optionally for the given minutes)

```text
!unban @username
```

- Remove user from the block list

```text
!bans
```

- Show the list of bans and reasons

```text
!ops @username
```

- Authorize someone else to be able to moderate

```text
!unops @username
```

- Remove someone from moderation

```text
!admin @username
```

- Authorize someone to be able to administrate

```text
!unadmin @username
```

- Remove someone from administrators

```text
!report ... ?
```

- Potentially have mods/admins be able to go in and manually change reports if need be

### Concerns / Thoughts / Ideas

- After a game is created, it needs to expire at some point
- After a report is done, how long until the report command stops working
- Does a user's game need to be reported before they can re-queue?
- What happens if a game is never reported on?
- When matchmaking w/ power levels, does it need to be a 100% match, +/- how much?
- What about using ELO to match make?

## 🤖 Running SpellBot

First install `spellbot` using [`pip`](https://pip.pypa.io/en/stable/):

```shell
pip install spellbot
```

Provide your Discord bot token with the environment variable `SPELLBOT_TOKEN`.

By default SpellBot will use sqlite3 as its database. You can however choose to
use another database by providing a [SQLAlchemy Connection URL][db-url]. This
can be done via the `--database-url` command line option or the environment
variable `SPELLBOT_DB_URL`. Note that, at the time of this writing, SpellBot is only
tested against sqlite3 and PostgreSQL.

More usage help can be found by running `spellbot --help`.

## 🐳 Docker Support

You can also run SpellBot via docker. See
[our documentation on Docker Support](DOCKER.md) for help.

## ❤️ Contributing

If you'd like to become a part of the SpellBot development community please first
know that we have a documented [code of conduct](CODE_OF_CONDUCT.md) and then
see our [documentation on how to contribute](CONTRIBUTING.md) for details on
how to get started.

---

[MIT][mit] © [amy@lexicalunit][lexicalunit] et [al][contributors]

[add-bot]:          https://discordapp.com/api/oauth2/authorize?client_id=725510263251402832&permissions=247872&scope=bot
[add-img]:          https://user-images.githubusercontent.com/1903876/82262797-71745100-9916-11ea-8b65-b3f656115e4f.png
[black-badge]:      https://img.shields.io/badge/code%20style-black-000000.svg
[black]:            https://github.com/psf/black
[build-badge]:      https://github.com/lexicalunit/spellbot/workflows/build/badge.svg
[build]:            https://github.com/lexicalunit/spellbot/actions
[codecov-badge]:    https://codecov.io/gh/lexicalunit/spellbot/branch/master/graph/badge.svg
[codecov]:          https://codecov.io/gh/lexicalunit/spellbot
[contributors]:     https://github.com/lexicalunit/spellbot/graphs/contributors
[db-url]:           https://docs.sqlalchemy.org/en/latest/core/engines.html
[lexicalunit]:      http://github.com/lexicalunit
[mit-badge]:        https://img.shields.io/badge/License-MIT-yellow.svg
[mit]:              https://opensource.org/licenses/MIT
[pypi-badge]:       https://img.shields.io/pypi/v/spellbot
[pypi]:             https://pypi.org/project/spellbot/
[python-badge]:     https://img.shields.io/badge/python-3.7+-blue.svg
[python]:           https://www.python.org/
[spelltable]:       https://www.spelltable.com/
