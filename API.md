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
