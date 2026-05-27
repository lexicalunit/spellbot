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
