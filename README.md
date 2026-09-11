# SpellBot

<div align="center">

<img
    width="200"
    alt="spellbot"
    src="https://raw.githubusercontent.com/lexicalunit/spellbot/main/spellbot.png"
/>
<br />
<br />
<a href="https://discord.com/api/oauth2/authorize?client_id=725510263251402832&permissions=2416045137&scope=applications.commands%20bot">
<img
        align="center"
        alt="Add to Discord"
        src="https://spellbot.io/assets/img/screenshots/spellbot-banner.png"
    />
</a>
<br />
The Discord bot for <a href="https://convoke.games/">Convoke</a>
<br />
<br />

|          <!-- --> |                                                                           <!-- -->                                                                            |
| ----------------: | :-----------------------------------------------------------------------------------------------------------------------------------------------------------: |
|    **Deployment** |                                   [![build][build-badge]][build] [![aws][aws-badge]][aws] [![status][status-badge]][status]                                   |
|  **Dependencies** |                                        [![python][python-badge]][python] [![discord.py][discord-py-badge]][discord-py]                                        |
|  **Distribution** |                                  [![pypi][pypi-badge]][pypi] [![docker][docker-badge]][docker-hub] [![mit][mit-badge]][mit]                                   |
|       **Quality** |                             [![codecov][codecov-badge]][codecov] [![ruff][ruff-badge]][ruff] [![pyright][pyright-badge]][pyright]                             |
| **Observability** | [![uptime][uptime-badge]][uptime] [![metrics][metrics-badge]][metrics]<br/>[![datadog][datadog-badge]][datadog] [![ganalytics][ganalytics-badge]][ganalytics] |
|       **Socials** |                                         [![discord][discord-badge]][discord-invite] [![follow][follow-badge]][follow]                                         |
|       **Funding** |                                              [![patreon][patreon-button]][patreon] [![kofi][kofi-button]][kofi]                                               |

</div>

## 🤖 Using SpellBot

SpellBot helps you find _Magic: The Gathering_ games on [Convoke][convoke], [Girudo][girudo], [Playgroup Live][playgroup], [EDHLAB][edhlab], and [Table Stream][tablestream]. Just looking to play a game of Commander? Run the command `/lfg` and SpellBot will help you out!

<p align="center">
    <img
        src="https://spellbot.io/assets/img/screenshots/lfg.png"
        width="600"
        alt="/lfg"
    />
</p>

Visit [live queues][queues], where you can log in with Discord to browse the games currently queuing across every server, filter them down to just the communities you play in, set up notifications so you're pinged when a game you care about is forming, and look back through your own game history and records.

## ✨ Everything you need to get started

- **One command to queue.** `/lfg` puts you in the queue. When the seats fill, SpellBot creates the table on the service your server plays on and posts the link, so nobody is left coordinating in chat.
- **Every server in one place.** [Browse games][queues] forming across every SpellBot community at once, filter to the servers you actually play in, and get pinged when a game you care about starts coming together.
- **Your games, on the record.** Look back through your own [history and records][queues], and keep a fuller picture of every match with the Mythic Track, Castlog and Playgroup Live integrations.

## 📚 Documentation

| <!-- --> | <!-- --> |
| :------- | :------- |
| [Getting Started](GETTING_STARTED.md) | Add the bot, run your first game, fix Direct Messages |
| [Features](FEATURES.md) | Matchmaking, live queues, and the Mythic Track, Playgroup Live and Castlog integrations |
| [Community](COMMUNITY.md) | Where to play, feedback, supporters, and contributing |
| [Administration](ADMINISTRATION.md) | Per-server and per-channel configuration commands |
| [Contributing](CONTRIBUTING.md) | Development setup and how to submit changes |
| [Integrations](INTEGRATIONS.md) | Adding support for a new play service |
| [API](API.md) | The public REST API |
| [Database](DATABASE.md) | Schema and migrations |
| [Docker](DOCKER.md) | Running SpellBot in a container |
| [Security](SECURITY.md) | Reporting a vulnerability |

## 🐳 Docker Support

SpellBot can be run via docker. Our image is published to [lexicalunit/spellbot][docker-hub]. See [our documentation on Docker Support](DOCKER.md) for help with installing and using it.

## 🙌 Supported By

The continued operation of SpellBot is supported by [PlayEDH](https://www.playedh.com/) as well as generous donations from [my patrons on Patreon][patreon] and [Ko-fi][kofi]. If you would like to help support SpellBot, please consider [signing up][patreon] for as little as _one dollar a month_ or [giving me a one-off tip][kofi] for whatever you feel is appropriate.

## ❤️ Contributing

If you'd like to become a part of the SpellBot development community please first know that we have a documented [code of conduct](CODE_OF_CONDUCT.md) and then see our [documentation on how to contribute](CONTRIBUTING.md) for details on how to get started.

## 🔍 Fine-print

Any usage of SpellBot implies that you accept the following policies.

- [Privacy Policy](PRIVACY_POLICY.md)
- [Terms of Service](TERMS_OF_SERVICE.md)

---

[MIT][mit] © [amy@lexicalunit][lexicalunit] et [al][contributors]

[aws-badge]: https://img.shields.io/badge/cloud-aws-green
[aws]: https://console.aws.amazon.com/console/home
[build-badge]: https://github.com/lexicalunit/spellbot/actions/workflows/ci.yaml/badge.svg
[build]: https://github.com/lexicalunit/spellbot/actions/workflows/ci.yaml
[codecov-badge]: https://codecov.io/gh/lexicalunit/spellbot/branch/main/graph/badge.svg
[codecov]: https://codecov.io/gh/lexicalunit/spellbot
[contributors]: https://github.com/lexicalunit/spellbot/graphs/contributors
[convoke]: https://www.convoke.games/
[datadog-badge]: https://img.shields.io/badge/monitors-datadog-blueviolet.svg
[datadog]: https://app.datadoghq.com/apm/home
[discord-badge]: https://img.shields.io/discord/949425995969093722?logo=Discord&logoColor=ffffff&labelColor=7289da
[discord-invite]: https://discord.gg/HuzTQYpYH4
[discord-py-badge]: https://img.shields.io/badge/discord.py-2.x.x-blue
[discord-py]: https://github.com/Rapptz/discord.py
[docker-badge]: https://img.shields.io/docker/pulls/lexicalunit/spellbot.svg
[docker-hub]: https://hub.docker.com/r/lexicalunit/spellbot
[edhlab]: https://edhlab.gg/
[follow-badge]: https://img.shields.io/badge/Bluesky-1185FE?style=flat&logo=bluesky&logoColor=white
[follow]: https://bsky.app/profile/spellbot.io
[ganalytics-badge]: https://img.shields.io/badge/analytics-google-orange.svg
[ganalytics]: https://analytics.google.com/analytics/web/
[girudo]: https://www.girudo.com/
[kofi-button]: https://img.shields.io/badge/Ko--fi-F16061?style=flat&logo=ko-fi&logoColor=white
[kofi]: https://ko-fi.com/lexicalunit
[lexicalunit]: http://github.com/lexicalunit
[metrics-badge]: https://img.shields.io/badge/metrics-dashboard-orange.svg
[metrics]: http://prod.app.spellbot.io/admin/dashboard
[mit-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
[mit]: https://opensource.org/license/mit
[patreon-button]: https://img.shields.io/badge/Patreon-F96854?style=flat&logo=patreon&logoColor=white
[patreon]: https://www.patreon.com/lexicalunit
[playgroup]: https://playgroup.gg/
[pypi-badge]: https://img.shields.io/pypi/v/spellbot
[pypi]: https://pypi.org/project/spellbot/
[pyright-badge]: https://img.shields.io/badge/types-pyright-c3c38f.svg
[pyright]: https://github.com/microsoft/pyright
[python-badge]: https://img.shields.io/badge/python-3.14-blue.svg
[python]: https://www.python.org/
[queues]: https://queues.spellbot.io
[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff]: https://github.com/astral-sh/ruff
[status-badge]: https://img.shields.io/badge/bot-status-green
[status]: https://status.spellbot.io
[tablestream]: https://table-stream.com/
[uptime-badge]: https://img.shields.io/uptimerobot/ratio/m785764282-c51c742e56a87d802968efcc
[uptime]: https://uptimerobot.com/dashboard#785764282
