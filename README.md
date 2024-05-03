# SpellBot

<div align="center">

<img
    width="200"
    alt="spellbot"
    src="https://raw.githubusercontent.com/lexicalunit/spellbot/main/spellbot.png"
/>
<br />
<br />
<a href="https://discordapp.com/api/oauth2/authorize?client_id=725510263251402832&permissions=2416045137&scope=applications.commands%20bot">
    <img
        align="center"
        alt="Add to Discord"
        src="https://user-images.githubusercontent.com/1903876/88951823-5d6c9a00-d24b-11ea-8523-d256ccbf4a3c.png"
    />
</a>
<br />
The Discord bot for <a href="https://spelltable.wizards.com/">SpellTable</a>
<br />
<br />

| <!-- --> | <!-- --> |
| ---: | :---: |
| **Deployment**    | [![build][build-badge]][build] [![heroku][heroku-badge]][heroku] |
| **Dependencies**  | [![python][python-badge]][python] [![discord.py][discord-py-badge]][discord-py] |
| **Distribution**  | [![pypi][pypi-badge]][pypi] [![docker][docker-badge]][docker-hub] [![mit][mit-badge]][mit] |
| **Quality**       | [![codecov][codecov-badge]][codecov] [![ruff][ruff-badge]][ruff] [![pyright][pyright-badge]][pyright] |
| **Observability** | [![uptime][uptime-badge]][uptime] [![metrics][metrics-badge]][metrics] [![datadog][datadog-badge]][datadog] |
| **Socials**       | [![discord][discord-badge]][discord-invite] [![follow][follow-badge]][follow] |
| **Funding**       | [![patreon][patreon-button]][patreon] |

</div>

## 🤖 Using SpellBot

SpellBot helps you find _Magic: The Gathering_ games on [SpellTable][spelltable]. Just looking to
play a game of Commander? Run the command `/lfg` and SpellBot will help you out!

<p align="center">
    <img
        src="https://github.com/lexicalunit/spellbot/assets/1903876/39381709-8dfd-473e-8072-e7267c50b4ad"
        width="600"
        alt="/lfg"
    />
</p>

SpellBot uses [Discord slash commands][slash]. Each command provides its own help documentation that
you can view directly within Discord itself before running the command. Take a look and see what's
available by typing `/` and browsing the commands for SpellBot!

## 🔭 Where to Play?

These communities are using SpellBot to play Magic! Maybe one of them is right for you?

<div align="center">
<!-- SERVERS BEGIN -->
<table>
    <tr>
        <td align="center"><a href="https://www.playedh.com/"><img width="200" height="200" src="https://user-images.githubusercontent.com/1903876/140843874-78510411-dcc8-4a26-a59a-0d6856698dcc.png" alt="PlayEDH" /><br />PlayEDH</a></td>
        <td align="center"><a href="https://discord.com/invite/cedh"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/8d5bbdce-a180-4e34-b25f-b95262b0fe63" alt="cEDH" /><br />cEDH</a></td>
        <td align="center"><a href="https://www.patreon.com/tolariancommunitycollege"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/92aa9c59-9f30-4f4e-83ab-fc86e72e8f40" alt="Tolarian Community College" /><br />Tolarian&nbsp;Community&nbsp;College</a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://disboard.org/server/815001383979450368"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/26b824c1-fa82-4b18-a47c-37114a0023b7" alt="EDH Fight Club" /><br />EDH&nbsp;Fight&nbsp;Club</a></td>
        <td align="center"><a href="https://disboard.org/server/757455940009328670"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/a2117868-cd86-44a9-8e92-91e5b2d639c2" alt="Oath of the Gaywatch" /><br />Oath&nbsp;of&nbsp;the&nbsp;Gaywatch</a></td>
        <td align="center"><a href="https://www.facebook.com/EDHTambayan/"><img width="200" height="200" src="https://user-images.githubusercontent.com/1903876/161825614-64e432d4-85e8-481e-8f41-f66ab8c940cc.png" alt="EDH Tambayan" /><br />EDH&nbsp;Tambayan</a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://www.playtowinmtg.com/"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/e04abae7-394e-4f89-94e9-edbdbfd411fb" alt="Play to Win" /><br />Play&nbsp;to&nbsp;Win</a></td>
        <td align="center"><a href="https://linktr.ee/cedhspain"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/823a2ed7-c59a-47da-886c-5f468a3b3032" alt="Comunidad Española de cEDH" /><br />Comunidad&nbsp;Española&nbsp;de&nbsp;cEDH</a></td>
        <td align="center"><a href="https://discord.gg/commander"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/a4f292c6-65b3-4767-8e82-f39c35a75723" alt="Commander RC" /><br />Commander&nbsp;RC</a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://discord.gg/ZmPsjrxe4h"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/47d68a5b-fe08-497c-a76b-c8dde5f56af3" alt="Command the Cause" /><br />Command&nbsp;the&nbsp;Cause</a></td>
        <td align="center"><a href="https://www.ka0stournaments.com/"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/104dc2da-4aad-4998-a778-479b54d1c600" alt="ka0s Tournaments" /><br />ka0s&nbsp;Tournaments</a></td>
        <td align="center"><a href="https://twitter.com/TurboDCommander"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/d7d6c867-c857-4760-8552-8b8e7b4a1bad" alt="Turbo Commander" /><br />Turbo&nbsp;Commander</a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://www.cedh.uk/"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/34bcb78c-60e2-495a-b919-873d0d331798" alt="cEDH UK" /><br />cEDH&nbsp;UK</a></td>
        <td align="center"><a href="https://disboard.org/server/689674672240984067"><img width="200" height="200" src="https://github.com/lexicalunit/spellbot/assets/1903876/322d1bdf-6b32-45f5-93b2-8d4963075772" alt="MTG@Home" /><br />MTG@Home</a></td>
    </tr>
</table>
<!-- SERVERS END -->
</div>

Want your community to be featured here as well? Please contact me at
[spellbot@lexicalunit.com](mailto:spellbot@lexicalunit.com)!

## ❓ Help

Two of the most common issues people using SpellBot run into are related to receiving Direct Messages from the bot. SpellBot uses Discord embeds in the DMs that it sends and there are some settings you need to enable for this to work correctly.

In your `Settings ► Chat` make sure that you have enabled **Embeds and link previews**.

<p align="center">
    <img
        src="https://github.com/lexicalunit/spellbot/assets/1903876/0d584532-0689-44b5-ba18-882d44b4b808"
        width="700"
        alt="Settings - Chat"
    />
</p>

And in your `Settings ► Privacy & Safety`, enable both **Allow direct message message for server members** and **Enable message requests from server members you may not know**.

<p align="center">
    <img
        src="https://github.com/lexicalunit/spellbot/assets/1903876/f16c943b-5120-4def-a254-d7fd04af2689"
        width="700"
        alt="Settings - Privacy & Safety"
    />
</p>

If you have more questions, please don't hesitate to join us on the [SpellBot Discord server][discord-invite] to get answers from our generous community.

## 🎤 Feedback

Thoughts and suggestions? Come join us on the [SpellBot Discord server][discord-invite]! Please
also feel free to [directly report any bugs][issues] that you encounter. Or reach out to me on
Twitter at [@SpellBotIO][follow].

## 🙌 Supported By

The continued operation of SpellBot is supported by <a href="https://www.playedh.com/">PlayEDH</a> as well as generous donations from [my patrons on Patreon][patreon]. If you would like to help support SpellBot, please consider [signing up][patreon] for as little a _one dollar a month_.

## ❤️ Contributing

If you'd like to become a part of the SpellBot development community please first know that we have
a documented [code of conduct](CODE_OF_CONDUCT.md) and then see our
[documentation on how to contribute](CONTRIBUTING.md) for details on how to get started.

## 🐳 Docker Support

SpellBot can be run via docker. Our image is published to
[lexicalunit/spellbot][docker-hub]. See [our documentation on Docker Support](DOCKER.md) for help
with installing and using it.

## 🔍 Fine-print

Any usage of SpellBot implies that you accept the following policies.

- [Privacy Policy](PRIVACY_POLICY.md)
- [Terms of Service](TERMS_OF_SERVICE.md)

---

[MIT][mit] © [amy@lexicalunit][lexicalunit] et [al][contributors]

[build-badge]: https://github.com/lexicalunit/spellbot/workflows/build/badge.svg
[build]: https://github.com/lexicalunit/spellbot/actions
[codecov-badge]: https://codecov.io/gh/lexicalunit/spellbot/branch/main/graph/badge.svg
[codecov]: https://codecov.io/gh/lexicalunit/spellbot
[contributors]: https://github.com/lexicalunit/spellbot/graphs/contributors
[datadog-badge]: https://img.shields.io/badge/monitors-datadog-blueviolet.svg
[datadog]: https://app.datadoghq.com/apm/home
[discord-badge]: https://github.com/lexicalunit/spellbot/assets/1903876/871aca88-3636-4c38-bcc1-f4093f89146f
[discord-invite]: https://discord.gg/HuzTQYpYH4
[discord-py-badge]: https://img.shields.io/badge/discord.py-2.1.0-blue
[discord-py]: https://github.com/Rapptz/discord.py
[docker-badge]: https://img.shields.io/docker/pulls/lexicalunit/spellbot.svg
[docker-hub]: https://hub.docker.com/r/lexicalunit/spellbot
[follow-badge]: https://img.shields.io/twitter/follow/SpellBotIO?style=social
[follow]: https://twitter.com/intent/follow?screen_name=SpellBotIO
[heroku-badge]: https://img.shields.io/badge/cloud-heroku-green
[heroku]: https://dashboard.heroku.com/apps/lexicalunit-spellbot
[issues]: https://github.com/lexicalunit/spellbot/issues
[lexicalunit]: http://github.com/lexicalunit
[metrics-badge]: https://img.shields.io/badge/metrics-grafana-orange.svg
[metrics]: https://lexicalunit.grafana.net/d/4TSUCbcMz/spellbot?orgId=1
[mit-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
[mit]: https://opensource.org/licenses/MIT
[patreon-button]: https://img.shields.io/badge/Patreon-F96854?style=flat&logo=patreon&logoColor=white
[patreon]: https://www.patreon.com/lexicalunit
[pypi-badge]: https://img.shields.io/pypi/v/spellbot
[pypi]: https://pypi.org/project/spellbot/
[pyright-badge]: https://img.shields.io/badge/types-pyright-c3c38f.svg
[pyright]: https://github.com/microsoft/pyright
[python-badge]: https://img.shields.io/badge/python-3.12-blue.svg
[python]: https://www.python.org/
[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff]: https://github.com/astral-sh/ruff
[slash]: https://discord.com/blog/slash-commands-are-here
[spelltable]: https://spelltable.wizards.com/
[uptime-badge]: https://img.shields.io/uptimerobot/ratio/m785764282-c51c742e56a87d802968efcc
[uptime]: https://uptimerobot.com/dashboard#785764282
