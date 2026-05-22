# Administration

Documentation for operators of the SpellBot admin dashboard.

## Admin dashboard authentication

The admin dashboard at `/admin/dashboard` is protected by Discord OAuth2. Only the bot owner and Discord users explicitly granted admin status may sign in.

### Required environment variables

| Variable             | Description                                                                                                    |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| `BOT_APPLICATION_ID` | The bot's Discord application (client) ID. Already used for the bot itself.                                    |
| `BOT_CLIENT_SECRET`  | The bot's Discord OAuth2 client secret. Obtain from the Discord developer portal.                              |
| `OWNER_XID`          | Discord user xid of the bot owner. Always granted dashboard access.                                            |
| `SESSION_SECRET_KEY` | A Fernet key used to encrypt admin session cookies. See [generating a session key](#generating-a-session-key). |
| `API_BASE_URL`       | The publicly reachable base URL of the bot's web server (e.g. `https://bot.spellbot.io`).                      |

### Granting and revoking admin access

Admin status is stored on the `users.is_admin` column and is managed by the bot owner with two text commands (only the user identified by `OWNER_XID` can run them):

| Command          | Effect                                                  |
| ---------------- | ------------------------------------------------------- |
| `!promote <xid>` | Grant the given Discord user admin dashboard access.    |
| `!demote <xid>`  | Revoke the given Discord user's admin dashboard access. |

Both commands accept a raw Discord user xid (e.g. `!promote 123456789012345678`). If the target user has never interacted with SpellBot, a row is created for them on the fly. The owner never needs to be promoted — `OWNER_XID` is always treated as admin regardless of the database state.

### Generating a session key

The session cookie used by the admin dashboard is encrypted with [Fernet][fernet] (AES-128-CBC + HMAC-SHA256). `SESSION_SECRET_KEY` must be a url-safe base64-encoded 32-byte key, in the exact format produced by `cryptography.fernet.Fernet.generate_key()`.

Generate one with:

```sh
make session-key
```

or directly:

```sh
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the generated value in your `.env` file (or your deployment's secret manager) as `SESSION_SECRET_KEY`. Keep it secret — anyone with the key can forge admin session cookies.

> If `SESSION_SECRET_KEY` is left unset, the server generates a fresh ephemeral key on startup. This is fine for local development but means that all admin sessions are invalidated on every restart, and the key cannot be shared between replicas.

### Discord developer portal setup

In the [Discord developer portal][dev-portal], open your bot's application and under **OAuth2 → Redirects** add:

```text
{API_BASE_URL}/admin/oauth/callback
```

For example, in production this is `https://bot.spellbot.io/admin/oauth/callback`.

The OAuth2 flow uses only the `identify` scope; no guild membership or message content access is requested.

### Sign-in flow

1. Visit `/admin/login` on the bot's web server.
2. You are redirected to Discord to approve the `identify` scope.
3. Discord redirects back to `/admin/oauth/callback` with an authorization code.
4. The server exchanges the code for an access token, identifies the Discord user, and verifies they are either `OWNER_XID` or have `is_admin=true` in the database.
5. On success an encrypted `spellbot_admin` cookie is set with a 24h TTL and the user is redirected to `/admin/dashboard`.
6. Sign out at any time with `POST /admin/logout`.

> Admin status is checked only at login. If you `!demote` a user, their existing session remains valid until it expires (up to 24h) or the session key is rotated. Restart the web server or rotate `SESSION_SECRET_KEY` to invalidate all sessions immediately.

### Rotating the session key

To invalidate every existing admin session (e.g. after suspected compromise), generate a new key with `make session-key`, replace `SESSION_SECRET_KEY` in your environment, and restart the web server. All previously issued cookies will fail to decrypt and users will be prompted to sign in again.

[fernet]: https://cryptography.io/en/latest/fernet/
[dev-portal]: https://discord.com/developers/applications
