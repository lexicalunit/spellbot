<img
    align="right"
    width="200"
    alt="spellbot"
    src="https://raw.githubusercontent.com/lexicalunit/spellbot/main/spellbot.png"
/>

# SpellBot

[![build][build-badge]][build]
[![uptime][uptime-badge]][uptime]
[![codecov][codecov-badge]][codecov]
[![heroku][heroku-badge]][heroku]
[![python][python-badge]][python]
[![pypi][pypi-badge]][pypi]
[![discord.py][discord-py-badge]][discord-py]
[![docker][docker-badge]][docker-hub]
[![black][black-badge]][black]
[![mit][mit-badge]][mit]
[![metrics][metrics-badge]][metrics]
[![datadog][datadog-badge]][datadog]
[![patreon][patreon-button]][patreon]
[![follow][follow-badge]][follow]

<br />
<br />
<br />
<br />
<p align="center">
    <a href="https://discordapp.com/api/oauth2/authorize?client_id=725510263251402832&permissions=2416045137&scope=applications.commands%20bot">
        <img
            align="center"
            alt="Add to Discord"
            src="https://user-images.githubusercontent.com/1903876/88951823-5d6c9a00-d24b-11ea-8523-d256ccbf4a3c.png"
        />
    </a>
    <br />
    The Discord bot for <a href="https://spelltable.wizards.com/">SpellTable</a>
</p>
<br />

## 🤖 Using SpellBot

SpellBot helps you find _Magic: The Gathering_ games on [SpellTable][spelltable]. Just looking to
play a game of Commander? Run the command `/lfg` and SpellBot will help you out!

<p align="center">
    <img
        src="https://user-images.githubusercontent.com/1903876/137987904-6fcdf273-5b60-4692-9389-a51d65c0a424.png"
        width="600"
        alt="/lfg"
    />
</p>

SpellBot uses [Discord slash commands][slash]. Each command provides its own help documentation that
you can view directly within Discord itself before running the command. Take a look and see what's
available by typing `/` and browsing the commands for SpellBot!

## 🔭 Where to Play?

These communities are using SpellBot to play Magic! Maybe one of them is right for you?

<table>
    <tr>
        <td align="center"><a href="https://www.playedh.com/"><img width="160" height="160" src="https://user-images.githubusercontent.com/1903876/140843874-78510411-dcc8-4a26-a59a-0d6856698dcc.png" alt="PlayEDH" /><br />PlayEDH</a></td>
        <td align="center"><a href="https://www.reddit.com/r/CompetitiveEDH/"><img width="160" height="160" src="https://user-images.githubusercontent.com/1903876/140865281-19774420-a49b-4d0e-bf0c-db3ad937022e.png" alt="r/cEDH" /><br />r/cEDH</a></td>
        <td align="center"><a href="https://www.patreon.com/tolariancommunitycollege"><img height="160" src="https://user-images.githubusercontent.com/1903876/184271392-39ca23ba-36d9-4aa0-a6e5-26af5e0acfc1.jpg" alt="Tolarian Community College" /><br /><span class="small">Tolarian&nbsp;Community&nbsp;College</span></a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://www.commandthecause.org/"><img width="160" height="160" src="https://user-images.githubusercontent.com/1903876/161826326-43cbd3ff-976f-46ff-9608-dacea67d9c42.png" alt="Command the Cause" /><br />Command&nbsp;the&nbsp;Cause</a></td>
        <td align="center"><a href="https://www.patreon.com/NitpickingNerds"><img height="160" src="https://user-images.githubusercontent.com/1903876/140844623-8d8528a9-b60c-49c6-be0f-1d627b85adba.png" alt="The Nitpicking Nerds" /><br />The&nbsp;Nitpicking&nbsp;Nerds</a></td>
        <td align="center"><a href="https://www.facebook.com/EDHTambayan/"><img height="160" src="https://user-images.githubusercontent.com/1903876/161825614-64e432d4-85e8-481e-8f41-f66ab8c940cc.png" alt="EDH Tambayan" /><br />EDH&nbsp;Tambayan</a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://disboard.org/server/752261529390284870"><img height="130" src="https://user-images.githubusercontent.com/1903876/140845571-12e391d0-4cc8-4766-bf40-071f32503a7d.jpg" alt="Commander SpellTable (DE)" /><br /><span class="small">Commander&nbsp;SpellTable&nbsp;(DE)</span></a></td>
        <td align="center"><a href="https://www.patreon.com/PlayingWithPowerMTG"><img height="130" src="https://user-images.githubusercontent.com/1903876/148892809-60b7d7f0-d773-4667-a863-829338d6aaed.png" alt="Playing with Power" /><br />Playing&nbsp;with&nbsp;Power</a></td>
        <td align="center"><a href="https://disboard.org/server/815001383979450368"><img height="130" src="https://user-images.githubusercontent.com/1903876/140863859-9ec1997b-9983-498e-9295-fa594d242b4d.jpg" alt="EDH Fight Club" /><br />EDH&nbsp;Fight&nbsp;Club</a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://discord.gg/Xc748UPh5B"><img height="140" src="https://user-images.githubusercontent.com/1903876/192328539-a575bb6a-5a87-4766-92b3-8f94fbc17914.png" alt="Budget Commander" /><br />Budget&nbsp;Commander</a></td>
        <td align="center"><a href="https://disboard.org/server/806995731268632596"><img height="140" src="https://user-images.githubusercontent.com/1903876/140845585-8053037f-a42b-4c1c-88f2-1b3c403fea09.jpg" alt="The Mages Guild" /><br />The&nbsp;Mages&nbsp;Guild</a></td>
        <td align="center"><a href="https://discord.gg/commander"><img height="140" src="https://user-images.githubusercontent.com/1903876/147596500-3cd08eef-84ad-4c02-a219-2eef0642a973.jpg" alt="Commander RC"/><br />Commander&nbsp;RC</a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://www.patreon.com/asylumgamingmtg"><img height="140" src="https://user-images.githubusercontent.com/1903876/198731021-a6ea0111-da86-42e3-b74b-79d1225a2849.png" alt="Asylum Gaming" /><br />Asylum&nbsp;Gaming</a></td>
        <td align="center"><a href="https://discord.gg/YeFrEqae3N"><img height="140" src="https://user-images.githubusercontent.com/1903876/148895425-0c72426c-d7dd-4974-99d7-21949f80e893.png" alt="コマンドフェストオンライン" /><br /><span class="small">コマンドフェストオンライン</span></a></td>
        <td align="center"><a href="https://disboard.org/server/848414032398516264"><img height="140" src="https://user-images.githubusercontent.com/1903876/140863856-00482a5a-7fe5-4cbb-8c4b-2442504925ea.jpg" alt="Commander en Español" /><br /><span class="small">Commander&nbsp;en&nbsp;Español</span></a></td>
    </tr>
    <tr>
        <td align="center"><a href="https://discord.gg/7gJDYU44gM"><img height="130" src="https://user-images.githubusercontent.com/1903876/147705994-909a94cc-ce70-431b-823a-127d257cdb52.png" alt="MTG let's play!!" /><br />MTG&nbsp;let&apos;s&nbsp;play!!</a></td>
        <td align="center"><a href="https://www.mtglandfall.com/"><img height="130" src="https://user-images.githubusercontent.com/1903876/152042910-af34b521-bba2-43d1-a033-d7fd7c387673.png" alt="Landfall" /><br />Landfall</a></td>
        <td align="center"><a href="https://discord.gg/Rgp3xaV7HU"><img height="130" src="https://user-images.githubusercontent.com/1903876/148823767-5e1feb59-37d8-4340-ae23-148d8415699f.png" alt="Torre de Mando" /><br />Torre&nbsp;de&nbsp;Mando</a></td>
    </tr>
    <tr>
        <td align="center">&nbsp;</td>
        <td align="center"><a href="https://discord.gg/xcnRz86vkb"><img height="130" src="https://user-images.githubusercontent.com/1903876/156637022-c8847db5-9cf5-4d00-a5b0-ecbaaec27802.jpg" alt="Your Virtual LGS" /><br />Your&nbsp;Virtual&nbsp;LGS</a></td>
        <td align="center">&nbsp;</td>
    </tr>
</table>

Want your community to be featured here as well? Please contact me at
[spellbot@lexicalunit.com](mailto:spellbot@lexicalunit.com)!

## 🎤 Feedback

Thoughts and suggestions? Come join us on the [SpellBot Discord server][discord-invite]! Please
also feel free to [directly report any bugs][issues] that you encounter. Or reach out to me on
Twitter at [@SpellBotIO][follow].

## 🙌 Support Me

I'm keeping SpellBot running using my own money but if you like the bot and want to help me out,
please consider [becoming a patron][patreon].

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

[black-badge]: https://img.shields.io/badge/code%20style-black-000000.svg
[black]: https://github.com/psf/black
[build-badge]: https://github.com/lexicalunit/spellbot/workflows/build/badge.svg
[build]: https://github.com/lexicalunit/spellbot/actions
[codecov-badge]: https://codecov.io/gh/lexicalunit/spellbot/branch/main/graph/badge.svg
[codecov]: https://codecov.io/gh/lexicalunit/spellbot
[contributors]: https://github.com/lexicalunit/spellbot/graphs/contributors
[datadog-badge]: https://img.shields.io/badge/monitors-datadog-blueviolet.svg
[datadog]: https://app.datadoghq.com/apm/home
[discord-invite]: https://discord.gg/HuzTQYpYH4
[discord-py-badge]: https://img.shields.io/badge/discord.py-2.0.1-blue
[discord-py]: https://github.com/Rapptz/discord.py
[docker-badge]: https://img.shields.io/docker/pulls/lexicalunit/spellbot.svg
[docker-hub]: https://hub.docker.com/r/lexicalunit/spellbot
[follow-badge]: https://img.shields.io/twitter/follow/SpellBotIO?style=social
[follow]: https://twitter.com/intent/follow?screen_name=SpellBotIO
[heroku-badge]: https://img.shields.io/badge/heroku-deployed-green
[heroku]: https://dashboard.heroku.com/apps/lexicalunit-spellbot
[issues]: https://github.com/lexicalunit/spellbot/issues
[lexicalunit]: http://github.com/lexicalunit
[metrics-badge]: https://img.shields.io/badge/metrics-grafana-orange.svg
[metrics]: https://lexicalunit.grafana.net/d/4TSUCbcMz/spellbot?orgId=1
[mit-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
[mit]: https://opensource.org/licenses/MIT
[patreon-button]: https://img.shields.io/endpoint.svg?url=https%3A%2F%2Fshieldsio-patreon.vercel.app%2Fapi%3Fusername%3Dlexicalunit%26type%3Dpatrons88951826-5e053080-d24b-11ea-9a81-f1b5431a5d4b.png
[patreon]: https://www.patreon.com/lexicalunit
[pypi-badge]: https://img.shields.io/pypi/v/spellbot
[pypi]: https://pypi.org/project/spellbot/
[python-badge]: https://img.shields.io/badge/python-3.10-blue.svg
[python]: https://www.python.org/
[security]: https://github.com/lexicalunit/spellbot/security
[slash]: https://discord.com/blog/slash-commands-are-here
[spelltable]: https://spelltable.wizards.com/
[uptime-badge]: https://img.shields.io/uptimerobot/ratio/m785764282-c51c742e56a87d802968efcc
[uptime]: https://uptimerobot.com/dashboard#785764282
