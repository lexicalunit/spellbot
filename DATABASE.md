# Database

Documentation on how to manage the database instance for SpellBot.

## Local development

For local development I recommend spinning up a local instance of Postgres. You can do this with Docker. For more details see [CONTRIBUTING.md](CONTRIBUTING.md#launch-dependencies).

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

Sometimes it's useful to have readonly access to the database. For example, when debugging a production issue. To do this, you can use the `psql` command line tool to connect to the database.

```sh
psql --host="$TARGET_HOST" \
  --username="$TARGET_USER" \
  --dbname="$TARGET_DB_NAME"
# You will be prompted to enter the password for the user.
```

Then to create the readonly user, run the following commands. Replace `OMIT` with a secure password.

```sql
create role spellbot_readonly_user with login password 'OMIT';
GRANT CONNECT ON DATABASE spellbot_prod TO spellbot_readonly_user;
GRANT USAGE ON SCHEMA public TO spellbot_readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO spellbot_readonly_user;
```

[alembic]: https://alembic.sqlalchemy.org/
[pg_dump]: https://docs.aws.amazon.com/dms/latest/sbs/chap-manageddatabases.postgresql-rds-postgresql-full-load-pd_dump.html
[pg_restore]: https://www.postgresql.org/docs/current/app-pgrestore.html
