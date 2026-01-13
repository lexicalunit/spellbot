# SpellBot API

SpellBot has a public API that can be used to access game and user data. As well as a few authenticated endpoints that can be used to manage game and user data.

**Base URL:** `https://prod.app.spellbot.io/`

- [Public Endpoints](#public-endpoints)
  - [GET `/`](#get-)
  - [GET `/status`](#get-status)
  - [GET `/g/{guild}/c/{channel}`](#get-gguildcchannel)
  - [GET `/g/{guild}/u/{user}`](#get-gguilduuser)
- [Authenticated Endpoints](#authenticated-endpoints)
  - [POST `/api/game/{game}/verify`](#post-apigamegameverify)
  - [POST `/api/game/{game}/record`](#post-apigamegamerecord)
  - [POST `/api/notification`](#post-apinotification)
  - [PATCH `/api/notification/{notif}`](#patch-apinotificationnotif)
  - [DELETE `/api/notification/{notif}`](#delete-apinotificationnotif)

## Public Endpoints

### GET `/`

Returns a 200 response with the text "ok" in the body.

### GET `/status`

Returns a HTML page with the current status of the bot.

### GET `/g/{guild}/c/{channel}`

Returns a HTML page with a list of games played in the given channel.

### GET `/g/{guild}/u/{user}`

Returns a HTML page with a list of games played by the given user.

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

#### Response

```json
{
  "result": {
    "success": true
  }
}
```

### POST `/api/notification`

This API is for external applications that want to create a notification in Discord for a game that was created outside of Discord. For example, a user might create a game on [Convoke](https://www.convoke.games/) and want to notify their friends in Discord that the game is ready to play.

> Note: Required API scope: `notification`.

#### Request

```json
{
  "link": "https://www.convoke.games/game/1234567890",
  "guild": 1234567890,
  "channel": 1234567890,
  "players": ["Alice", "Bob"],
  "format": 1,
  "bracket": 1,
  "service": 1,
  "role": 1234567890 // Optional: The role to ping when the notification is sent
}
```

**Brackets:**

| Value | Description |
| --- | --- |
| 1 | None |
| 2 | Bracket 1: Exhibition |
| 3 | Bracket 2: Core |
| 4 | Bracket 3: Upgraded |
| 5 | Bracket 4: Optimized |
| 6 | Bracket 5: Competitive |

**Formats:**

| Value | Description |
| --- | --- |
| 1 | Commander |
| 2 | Standard |
| 3 | Sealed |
| 4 | Modern |
| 5 | Vintage |
| 6 | Legacy |
| 7 | Brawl (Two Players) |
| 8 | Brawl (Multiplayer) |
| 9 | Two Headed Giant |
| 10 | Pauper |
| 11 | Pioneer |
| 12 | EDH Max |
| 13 | EDH High |
| 14 | EDH Mid |
| 15 | EDH Low |
| 16 | EDH Battlecruiser |
| 17 | Planechase |
| 18 | Commander Precons |
| 19 | Oathbreaker |
| 20 | Duel Commander |
| 21 | cEDH |
| 22 | Archenemy |
| 23 | Pauper EDH |
| 24 | Horde Magic |

**Services:**

| Value | Description |
| --- | --- |
| 1 | Not any |
| 2 | SpellTable |
| 3 | Cockatrice |
| 4 | XMage |
| 5 | MTG Arena |
| 6 | MTG Online |
| 7 | TabletopSim |
| 8 | Table Stream |
| 9 | Convoke |

#### Response

```json
{
  "result": {
    "success": true,
    "id": 1234567890
  }
}
```

### PATCH `/api/notification/{notif}`

This is for updating notifications created with `POST /api/notification`. You can update the list of players and/or mark the game as started.

> Note: Required API scope: `notification`.

#### Request

```json
{
  "players": ["Alice", "Bob"],
  "started_at": "2025-12-05T12:00:00Z"
}
```

#### Response

```json
{
  "result": {
    "success": true
  }
}
```

### DELETE `/api/notification/{notif}`

This is for deleting notifications created with `POST /api/notification`. Useful for expired or abandoned games.

> Note: Required API scope: `notification`.

#### Request

None

#### Response

```json
{
  "result": {
    "success": true
  }
}
```
