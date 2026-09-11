# Features

What SpellBot does for your playgroup.

## 🤝 Matchmaking

`/lfg` posts a game other players can join, and SpellBot keeps track of the seats. When the game fills it creates the table on the service your server plays on — [Convoke][convoke], [Playgroup Live][playgroup], [EDHLAB][edhlab], [Girudo][girudo] or [Table Stream][tablestream] — and shares the link with everyone who joined.

<p align="center">
    <img
        src="https://spellbot.io/assets/img/screenshots/lfg.png"
        width="600"
        alt="The embed SpellBot posts after running the /lfg command"
    />
</p>

Games can be filtered by format and bracket, players can block others they'd rather not be matched with, and admins can set per-channel defaults. See [Administration](ADMINISTRATION.md) for the full list.

## 📡 Live queues

[Live queues][queues] shows every game forming across every SpellBot community at once. Log in with Discord to filter down to just the servers you play in, set up notifications so you're pinged when a game you care about is forming, and look back through your own game history and records.

## 📊 Mythic Track

SpellBot integrates seamlessly with [Mythic Track](https://www.mythictrack.com/spellbot) which allows you to track games within your Discord server. Visualize and explore your data to reveal interesting trends. To get started run the `/setup_mythic_track` command on your server. Please also consider [supporting Mythic Track](https://www.patreon.com/MythicTrack)!

<p align="center">
    <img
        src="https://spellbot.io/assets/img/screenshots/mythic-track-setup.png"
        width="617"
        alt="Running the /setup_mythic_track command in Discord"
    />
</p>

## 🎲 Playgroup Live

SpellBot can also seat your games on [Playgroup Live](https://playgroup.gg/playgroup-live), creating a table for up to six players with starting life totals that match the format you queued for. One player in the game needs to connect their account first: run the `/playgroup link` command and SpellBot will find your Playgroup Live account and remember it for future games.

## 🎥 Castlog

SpellBot keeps a history of your games on [Castlog](https://castlog.gg/). When the result of a game is reported, SpellBot forwards the match on and Castlog builds a page for it, then links that page back to the game so you can find it later. Players who have connected their Castlog account are credited on the match automatically. Castlog's [SpellBot setup guide](https://castlog.gg/features/spellbot) walks through getting started.

## 🔌 Adding a service

Want SpellBot to support another play service? [Integrations](INTEGRATIONS.md) documents everything needed to add one.

---

[Getting Started](GETTING_STARTED.md) · [Community](COMMUNITY.md) · [Back to README](README.md)

[convoke]: https://www.convoke.games/
[edhlab]: https://edhlab.gg/
[girudo]: https://www.girudo.com/
[playgroup]: https://playgroup.gg/
[queues]: https://queues.spellbot.io
[tablestream]: https://table-stream.com/
