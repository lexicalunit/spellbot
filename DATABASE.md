# Database

Documentation on how to manage the database instance for SpellBot.

## Local development

For local development I recommend spinning up a local instance of Postgres. You can do this with Docker. For more details see [CONTRIBUTING.md](CONTRIBUTING.md#launch-dependencies). To fill it with real data, see [Local snapshot of production](#local-snapshot-of-production).

## Database migrations

We use [alembic][alembic] for database migrations. It can detect changes you've made compared to an existing database and generate migration scripts necessary to apply _and_ reverse those changes. First, make the changes to the data models. Alembic can detect differences between an existing database and changes made to the models. To autogenerate migration scripts that will bring the database inline with the changes you've made to the models, run:

```shell
uv run scripts/create_db_revision.py \
    "<your-sqlalchemy-database-url>" \
    "<Some description of your changes>"
```

> Note: An example database url: postgresql+psycopg://postgres@localhost:5432/postgres

This will create a revision script in the `src/spellbot/versions/versions` directory with a name like `REVISIONID_some_description_of_your_changes.py`. You may have to edit this script manually to ensure that it is correct as the autogenerate facility of `alembic revision` is not perfect.

## Reversing migrations

Another migration script is `scripts/downgrade.py` which allows you to pass a revision string to downgrade to. For example, to undo the last migration you could run something like:

```shell
uv run scripts/downgrade.py postgresql+psycopg://postgres@localhost:5432/postgres "-1"
```

## Managing backups

When migration from one instance to another you will need to dump the current state of the database and then restore it on the new instance.

Use [`pg_dump`][pg_dump] to dump the database to a file.

```sh
SOURCE_USER="YOUR_SOURCE_USERNAME"
SOURCE_PASS="YOUR_SOURCE_PASSWORD"
SOURCE_HOST="YOUR_SOURCE_HOSTNAME"
SOURCE_DB_NAME="YOUR_SOURCE_DATABASE_NAME"
SOURCE_DB_URL="postgres://${SOURCE_USER}:${SOURCE_PASS}@${SOURCE_HOST}:5432/${SOURCE_DB_NAME}"
pg_dump -Fc --no-acl --no-owner "$SOURCE_DB_URL" > spellbot.dump
```

Then use [`pg_restore`][pg_restore] to restore the database from that file.

```sh
TARGET_USER="YOUR_TARGET_USERNAME"
TARGET_PASS="YOUR_TARGET_PASSWORD"
TARGET_HOST="YOUR_TARGET_HOSTNAME"
TARGET_DB_NAME="YOUR_TARGET_DATABASE_NAME"
# Note: Target owner might have less permissions than the user doing the restoration.
#       If not, you can just use the same user as TARGET_USER here.
TARGET_OWNER="YOUR_TARGET_OWNER"
pg_restore \
  --host="$TARGET_HOST" \
  --username="$TARGET_USER" \
  --dbname="$TARGET_DB_NAME" \
  --clean --if-exists \
  --no-owner --no-privileges \
  --role="$TARGET_OWNER" \
  --jobs=$(($(nproc) / 2)) \
  ./spellbot.dump
```

## Readonly access

Sometimes it's useful to have readonly access to the production database, for example when debugging a production issue or [taking a snapshot for local testing](#local-snapshot-of-production).

The commands below use these placeholders. Replace them with the values for your deployment:

| Placeholder                                         | Meaning                                                                   |
| --------------------------------------------------- | ------------------------------------------------------------------------- |
| `YOUR_HOST` / `your_host`                           | Hostname of your production database                                      |
| `YOUR_DATABASE_NAME` / `your_database_name`         | Name of your production database                                          |
| `YOUR_ADMIN_USERNAME` / `your_admin_username`       | Admin user that can create roles and grant privileges                     |
| `your_app_username`                                 | Role SpellBot connects as. It runs the migrations, so it owns the tables. |
| `YOUR_READONLY_USERNAME` / `your_readonly_username` | The readonly user you are creating                                        |

Hosted databases usually require SSL. If yours does, run `export PGSSLMODE=require` first, so every `psql`, `pg_dump`, and `pg_restore` command below uses it.

### Creating the readonly user

Connect to your database as the admin user:

```sh
psql --host="$YOUR_HOST" \
     --username="$YOUR_ADMIN_USERNAME" \
     --dbname="$YOUR_DATABASE_NAME"
```

Then run the following, replacing `OMIT` with a secure password:

```sql
CREATE ROLE your_readonly_username WITH LOGIN PASSWORD 'OMIT';
GRANT CONNECT ON DATABASE your_database_name TO your_readonly_username;

-- Everything that exists today: application data and the settings audit history.
GRANT USAGE ON SCHEMA public, audit TO your_readonly_username;
GRANT SELECT ON ALL TABLES IN SCHEMA public, audit TO your_readonly_username;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public, audit TO your_readonly_username;

-- Everything future migrations create. Default privileges apply to objects created by a
-- specific role, so they must be set for the app role, which runs the migrations. Setting
-- them requires membership in that role. On managed services such as Amazon RDS and Aurora
-- the admin user isn't a true superuser, so it joins the role temporarily.
GRANT your_app_username TO your_admin_username;
ALTER DEFAULT PRIVILEGES FOR ROLE your_app_username IN SCHEMA public
  GRANT SELECT ON TABLES TO your_readonly_username;
ALTER DEFAULT PRIVILEGES FOR ROLE your_app_username IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO your_readonly_username;
REVOKE your_app_username FROM your_admin_username;
```

If your admin user is a real superuser, which is the case on a self-hosted Postgres, you can skip the `GRANT` and `REVOKE` lines around the default privileges.

Sequences need their own grant: `ALL TABLES` does not cover them, and without it `pg_dump` fails with "permission denied for sequence". The default privileges only cover the `public` schema. If a migration ever adds a new table or sequence to the `audit` schema, re-run the `audit` grants above.

You can check that the readonly user can read everything. This should report the same number twice:

```sql
SELECT count(*) FILTER (WHERE CASE WHEN c.relkind = 'S'
         THEN has_sequence_privilege('your_readonly_username', c.oid, 'SELECT')
         ELSE has_table_privilege('your_readonly_username', c.oid, 'SELECT') END) AS readable,
       count(*) AS total
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('public', 'audit') AND c.relkind IN ('r', 'p', 'S');
```

### Connecting as the readonly user

If your database has a read replica, connect to that instead of the primary to keep your queries off the instance serving the bot. On Amazon Aurora, for example, that is the cluster's reader endpoint.

To avoid typing the password, and to keep it out of your shell history, store it in [`~/.pgpass`][pgpass] and restrict the file's permissions. The file has one line per connection, in the format `your_host:5432:your_database_name:your_readonly_username:password`. In the password, put a backslash before any `:` or `\`. `psql`, `pg_dump`, and `pg_restore` all read the file automatically.

```sh
chmod 600 ~/.pgpass
psql --host="$YOUR_HOST" \
     --username="$YOUR_READONLY_USERNAME" \
     --dbname="$YOUR_DATABASE_NAME"
```

## Local snapshot of production

To see how the bot or the website behaves against real data, you can copy production into your local database.

> [!CAUTION]
> A snapshot contains real user data: Discord user IDs, usernames, and game history. Keep it on your machine, never commit or share it, and delete the dump file when you're done. The recipe below leaves out the contents of the `tokens` table so that live REST API keys never leave production.

### Prerequisites

- **PostgreSQL client tools at least as new as your production server.** `pg_dump` refuses to dump a server newer than itself. On macOS the easiest way to get them is Homebrew's `libpq`, which is keg-only, so add it to your `PATH`:

  ```sh
  brew install libpq
  export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
  ```

- **The local Postgres container running.** See [CONTRIBUTING.md](CONTRIBUTING.md#launch-dependencies).
- **The [readonly user](#readonly-access)**, with all of its grants and its password in `~/.pgpass`.

### 1. Dump production

```sh
SNAPSHOT_DIR="$HOME/spellbot-snapshot"

rm -rf "$SNAPSHOT_DIR"
pg_dump \
  --host="$YOUR_HOST" \
  --username="$YOUR_READONLY_USERNAME" \
  --dbname="$YOUR_DATABASE_NAME" \
  --format=directory --jobs=4 --file="$SNAPSHOT_DIR" \
  --no-owner --no-privileges \
  --exclude-table-data=public.tokens
```

The directory format with `--jobs` dumps several tables in parallel, which makes the dump a lot faster.

### 2. Recreate your local database

Set `LOCAL_DB` to the database named at the end of the `DATABASE_URL` in your `.env` file. If `DATABASE_URL` isn't set, it's `postgres`. This **replaces everything** in that local database:

```sh
LOCAL_DB="postgres"
docker exec spellbot-postgres psql -U postgres \
  -c "DROP DATABASE IF EXISTS \"$LOCAL_DB\" WITH (FORCE)" \
  -c "CREATE DATABASE \"$LOCAL_DB\""
```

If you want to keep your current local data, rename that database to something else first instead of dropping it, for example `ALTER DATABASE "postgres" RENAME TO "postgres-backup"`. Note that you can't rename `postgres` while you're connected to it, so run that from a different database.

### 3. Restore the snapshot

```sh
pg_restore \
  --host=localhost \
  --username=postgres \
  --dbname="$LOCAL_DB" \
  --no-owner --no-privileges \
  --jobs=4 \
  "$SNAPSHOT_DIR"
```

This should finish without errors. If you see "schema "audit" does not exist" errors, the dump was taken without access to the `audit` schema; fix the readonly user's grants and take the dump again.

### 4. Start SpellBot and clean up

Start the app as usual, for example with `make dev`. On startup it runs any migrations your branch has that production doesn't yet, so the database ends up matching your code. Then delete the dump:

```sh
rm -rf "$SNAPSHOT_DIR"
```

Because `tokens` is empty in the snapshot, the REST API won't accept any of production's keys locally. If you need one, sign in as the owner and create it in the **API Tokens** panel on `/admin/dashboard` (see [ADMINISTRATION.md](ADMINISTRATION.md#api-tokens)). Any data that only exists going forward, such as newly added columns, will be empty or have default values for existing rows.

[alembic]: https://alembic.sqlalchemy.org/
[pg_dump]: https://www.postgresql.org/docs/current/app-pgdump.html
[pg_restore]: https://www.postgresql.org/docs/current/app-pgrestore.html
[pgpass]: https://www.postgresql.org/docs/current/libpq-pgpass.html
