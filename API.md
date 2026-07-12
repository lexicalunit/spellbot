# SpellBot API

SpellBot has a public API that can be used to access game and user data. As well as a few authenticated endpoints that can be used to manage game and user data.

**Base URL:** `https://prod.app.spellbot.io/`

- [Public Endpoints](#public-endpoints)
  - [GET `/`](#get-)
  - [GET `/status`](#get-status)
  - [GET `/status.json`](#get-statusjson)
  - [GET `/g/{guild}/c/{channel}`](#get-gguildcchannel)
  - [GET `/g/{guild}/u/{user}`](#get-gguilduuser)
  - [GET `/queues.json`](#get-queuesjson)
- [Authenticated Endpoints](#authenticated-endpoints)
  - [POST `/api/game/{game}/verify`](#post-apigamegameverify)
  - [POST `/api/game/{game}/record`](#post-apigamegamerecord)
  - [POST `/api/game/{game}/metadata`](#post-apigamegamemetadata)

## Public Endpoints

### GET `/`

Returns a 200 response with the text "ok" in the body.

### GET `/status`

Returns a HTML page with the current status of the bot.

### GET `/status.json`

Returns the current status of the bot as JSON. This is similar to the [Discord Status API](https://discordstatus.com/api).

#### Response

```json
{
  "status": {
    "indicator": "operational",
    "description": "All Systems Operational"
  },
  "shards": {
    "total": 2,
    "ready": 2,
    "data": [
      {
        "shard_id": 0,
        "latency_ms": 45.5,
        "guild_count": 100,
        "is_ready": true,
        "last_updated": "2026-05-08T12:00:00+00:00",
        "version": "10.5.0"
      }
    ]
  },
  "guilds": 250,
  "version": "10.5.0",
  "upgrade_in_progress": false,
  "last_updated": "2026-05-08T12:00:00+00:00"
}
```

#### Status Indicators

| Indicator              | Description                                      |
| ---------------------- | ------------------------------------------------ |
| `operational`          | All Systems Operational                          |
| `degraded_performance` | Some shards are down                             |
| `major_outage`         | All shards are down                              |
| `maintenance`          | Upgrade in progress (multiple versions detected) |
| `unknown`              | No status data available                         |

### GET `/g/{guild}/c/{channel}`

Returns a HTML page with a list of games played in the given channel.

### GET `/g/{guild}/u/{user}`

Returns a HTML page with a list of games played by the given user.

### GET `/queues.json`

Returns the public list of pending queues currently waiting for players, the list of games that started in the last two hours, and an aggregate `active_games` stat. Queues with no players are omitted. Queue rows are ordered with the shortest wait first; started games are ordered newest first.

#### Query Parameters

| Parameter      | Type     | Description                                                                                                                                                              |
| -------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `mythic_track` | `string` | When set to `1`, restricts the `queues` list, the `games` list, and the `stats.active_games` count to guilds that have mythic track enabled. Any other value is ignored. |

#### Response

```json
{
  "stats": {
    "active_games": 12
  },
  "queues": [
    {
      "guild_xid": 980001,
      "guild_name": "Example Server",
      "guild_locale": "en",
      "logo": "https://cdn.discordapp.com/icons/980001/abc.png",
      "format": "Commander",
      "bracket": "Bracket 3: Upgraded",
      "service": "Convoke",
      "players": 2,
      "seats": 4,
      "wait_seconds": 480,
      "jump_url": "https://discord.com/channels/980001/980101/999999"
    }
  ],
  "games": [
    {
      "guild_xid": 980001,
      "guild_name": "Example Server",
      "guild_locale": "en",
      "logo": "https://cdn.discordapp.com/icons/980001/abc.png",
      "format": "Modern",
      "bracket": "None",
      "service": "Convoke",
      "seats": 2,
      "started_seconds_ago": 1800,
      "jump_url": "https://discord.com/channels/980001/980101"
    }
  ]
}
```

#### Fields

| Field                         | Type      | Description                                                                                      |
| ----------------------------- | --------- | ------------------------------------------------------------------------------------------------ |
| `stats.active_games`          | `integer` | Number of games started across all public guilds within the last two hours. Equals `len(games)`. |
| `queues[].guild_xid`          | `integer` | Discord snowflake of the guild hosting the queue.                                                |
| `queues[].guild_name`         | `string`  | Display name of the guild.                                                                       |
| `queues[].guild_locale`       | `string`  | BCP-47-ish locale code recorded for the guild (e.g., `en`, `ja`).                                |
| `queues[].logo`               | `string`  | URL of the guild's Discord icon, with a SpellBot default falling in when no icon is available.   |
| `queues[].format`             | `string`  | Human-readable game format (e.g., `Commander`, `Modern`).                                        |
| `queues[].bracket`            | `string`  | Human-readable commander bracket (e.g., `Bracket 3: Upgraded`, `None`).                          |
| `queues[].service`            | `string`  | Game service the queue will use (e.g., `Convoke`, `SpellTable`).                                 |
| `queues[].players`            | `integer` | Number of players currently queued.                                                              |
| `queues[].seats`              | `integer` | Total seats available in the game.                                                               |
| `queues[].wait_seconds`       | `integer` | Seconds elapsed since the queue was created.                                                     |
| `queues[].jump_url`           | `string`  | Discord deep-link to the originating channel or message.                                         |
| `games[].guild_xid`           | `integer` | Discord snowflake of the guild that hosted the started game.                                     |
| `games[].guild_name`          | `string`  | Display name of the guild.                                                                       |
| `games[].guild_locale`        | `string`  | BCP-47-ish locale code recorded for the guild (e.g., `en`, `ja`).                                |
| `games[].logo`                | `string`  | URL of the guild's Discord icon, with a SpellBot default falling in when no icon is available.   |
| `games[].format`              | `string`  | Human-readable game format (e.g., `Commander`, `Modern`).                                        |
| `games[].bracket`             | `string`  | Human-readable commander bracket (e.g., `Bracket 3: Upgraded`, `None`).                          |
| `games[].service`             | `string`  | Game service the game is using (e.g., `Convoke`, `SpellTable`).                                  |
| `games[].seats`               | `integer` | Total seats in the game.                                                                         |
| `games[].started_seconds_ago` | `integer` | Seconds elapsed since the game started.                                                          |
| `games[].jump_url`            | `string`  | Discord deep-link to the originating channel.                                                    |

## Authenticated Endpoints

All authenticated endpoints require a valid API token to be passed in the `Authorization` header. The token should be prefixed with `"Bearer "`.

> Note: API tokens are scoped to certain endpoints. Just because you have an API token does not mean that all authenticated endpoints are accessible.

If there is an error processing these requests, the response will follow the following format:

```json
{
  "error": "Something went wrong"
}
```

### POST `/api/game/{game}/verify`

Verifies the user's PIN for the given game for the given guild. This API is for external applications that track a user's game history, such as [Mythic Track](https://www.mythictrack.com/).

> Note: Required API scope: `game`.

#### Request

```json
{
  "user_xid": 1234567890,
  "guild_xid": 1234567890,
  "pin": "123456"
}
```

#### Response

```json
{
  "result": {
    "verified": true
  }
}
```

### POST `/api/game/{game}/record`

Records the given game as played by the given users and their commanders. This will send a DM to each user with the game record, informing them that the game was recorded. This API is for external applications that track a user's game history, such as [Mythic Track](https://www.mythictrack.com/).

> Note: Required API scope: `game`.

#### Request

```json
{
  "players": [
    {
      "xid": 1234567890,
      "commander": "Urza, Lord High Artificer"
    },
    {
      "xid": 1234567890,
      "commander": "Najeela, the Blade Blossom"
    }
  ],
  "winner": 1234567890,
  "tracker": 1234567890
}
```

> Note: for compatibility reasons, you can also pass a user name instead of an xid. If the user can be matched to a user in the SpellBot database by that name, processing will continue without error.

#### Response

```json
{
  "result": {
    "success": true
  }
}
```

### POST `/api/game/{game}/metadata`

Stores a post-game report for the given game. This is intended for the game service (e.g. [Convoke](https://commander.online/)) to report back match results that SpellBot's own database does not track, such as the match duration, the winner, each player's commander, and links to external trackers. The report is shown on the game's public detail page.

The request body is a free-form JSON object and is stored (mostly) verbatim, replacing any previously reported metadata for the game. SpellBot's game detail page understands the fields below and renders anything else it is given as-is; all fields are optional.

A few rules are enforced on write:

- If the stored report has a `reported_at` newer than the incoming one, the incoming report is **accepted but ignored** (still returns `success: true`). This keeps a delayed write from clobbering a newer, richer report. Always send a `reported_at`.
- `players` is capped at 64 entries and `links` at 32 entries; exceeding either is a `400`.
- Each `links` value must be an `http(s)` URL. Other values (e.g. `javascript:` URIs) are dropped before storage.

> Note: Required API scope: `game`.

#### Request

```json
{
  "source": "convoke",
  "reported_at": "2026-07-11T18:30:00+00:00",
  "started_at": "2026-07-11T17:45:00+00:00",
  "ended_at": "2026-07-11T18:27:00+00:00",
  "duration_minutes": 42,
  "turns": 12,
  "winner": {
    "xid": 1234567890,
    "name": "Alice",
    "commander": "Najeela, the Blade Blossom"
  },
  "players": [
    {
      "xid": 1234567890,
      "name": "Alice",
      "commander": "Najeela, the Blade Blossom",
      "commander_partner": null,
      "turn_order": 1,
      "time_minutes": 10,
      "is_winner": true
    },
    {
      "xid": 9876543210,
      "name": "Bob",
      "commander": "Urza, Lord High Artificer",
      "turn_order": 2,
      "is_winner": false
    }
  ],
  "links": {
    "mythic_track": "https://www.mythictrack.com/g/abc123",
    "playnice": "https://playnicemtg.com/g/xyz789"
  }
}
```

| Field              | Type             | Description                                                            |
| ------------------ | ---------------- | ---------------------------------------------------------------------- |
| `source`           | `string`         | The service that produced the report (e.g. `convoke`).                 |
| `reported_at`      | `string`         | ISO-8601 timestamp of when the report was generated.                   |
| `started_at`       | `string`         | ISO-8601 timestamp of when the match started.                          |
| `ended_at`         | `string`         | ISO-8601 timestamp of when the match ended.                            |
| `duration_minutes` | `number`         | Total match time in minutes.                                           |
| `turns`            | `number`         | Total number of turns played.                                          |
| `winner`           | `object`, `null` | The winning player (`xid`, `name`, `commander`), or `null` for a draw. |
| `players`          | `array`          | Per-player results (see fields below).                                 |
| `links`            | `object`         | Map of tracker name to URL. Keys are shown title-cased.                |

Each entry in `players` may include:

- `xid` — the player's Discord user ID, when known.
- `name` — the player's display name.
- `commander` — the player's commander.
- `commander_partner` — the player's partner/background commander, when applicable.
- `turn_order` — the player's seat/turn order (1-based).
- `time_minutes` — the player's total play time in minutes, when tracked.
- `is_winner` — `true` for the winning player(s).

#### Response

```json
{
  "result": {
    "success": true
  }
}
```
