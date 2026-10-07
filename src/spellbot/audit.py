# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Settings-change audit trail, using trigger SQL adapted from the `postgresql-audit` library.

Auditing is performed entirely by PostgreSQL statement-level triggers installed on the
`channels` and `guilds` tables (see the `..._install_settings_audit` migration). The triggers
record every settings change — whether it originates from the web admin (Core `UPDATE`s) or a
Discord command — into the `audit.activity` table, computing the per-column old/new diff and
skipping rows where nothing (outside the excluded columns) changed.

What this module owns is **actor attribution**. The triggers link each `audit.activity` row to a
row in `audit.transaction` by matching `pg_current_xact_id()`, so to record *who* made a change we
insert a transaction row carrying the actor — `actor_id`, `actor_name`, `source` — earlier in the
same database transaction as the change. The acting user is supplied ambiently via a context
variable (mirroring `DatabaseSession`'s context-local), set by the web handlers and `AdminAction`,
and read by `stamp()` at the settings-write choke points.

The audit tables and trigger SQL (in `audit_sql/`) were adapted from `postgresql-audit` 0.18.0,
which we no longer depend on: we only ever used its models and trigger SQL (its session listeners
are unsafe under our `AsyncSession`), and its `sqlalchemy-utils` dependency blocked SQLAlchemy
upgrades. The schema and triggers are unchanged from what the library installed.
"""

from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Any, cast

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from spellbot.database import DatabaseSession
from spellbot.models import Base, Channel, Guild, web_editable_columns

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from sqlalchemy.engine import Connection

AUDIT_SCHEMA = "audit"
AUDIT_SQL_DIR = Path(__file__).resolve().parent / "audit_sql"

# Sources recorded on `audit.transaction.source`.
SOURCE_WEB = "web"
SOURCE_DISCORD = "discord"


@dataclass(frozen=True)
class Actor:
    """The user a settings change is attributed to, and where it came from."""

    xid: int | None
    name: str | None
    source: str


class XID8(UserDefinedType[int]):
    """PostgreSQL's 64-bit transaction ID type, as returned by `pg_current_xact_id()`."""

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "XID8"


class Transaction(Base):
    """One DB transaction that changed audited settings, and the actor who made it."""

    __tablename__ = "transaction"
    __table_args__ = (
        sa.UniqueConstraint("native_transaction_id", name="transaction_unique_native_tx_id"),
        {"schema": AUDIT_SCHEMA},
    )

    # Discord snowflakes exceed 32 bits, so actor_id must be a BigInteger.
    actor_id: Mapped[int | None] = mapped_column(sa.BigInteger, index=True)
    actor_name: Mapped[str | None] = mapped_column(sa.Text)
    source: Mapped[str | None] = mapped_column(sa.Text)
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    native_transaction_id: Mapped[int | None] = mapped_column(XID8())
    issued_at: Mapped[datetime | None] = mapped_column(sa.DateTime)
    client_addr: Mapped[str | None] = mapped_column(INET)


class Activity(Base):
    """One audited row change, written by the `create_activity()` trigger function."""

    __tablename__ = "activity"
    __table_args__ = {"schema": AUDIT_SCHEMA}  # noqa: RUF012

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    schema_name: Mapped[str | None] = mapped_column(sa.Text)
    table_name: Mapped[str | None] = mapped_column(sa.Text)
    relid: Mapped[int | None] = mapped_column(sa.Integer)
    issued_at: Mapped[datetime | None] = mapped_column(sa.DateTime)
    native_transaction_id: Mapped[int | None] = mapped_column(XID8(), index=True)
    verb: Mapped[str | None] = mapped_column(sa.Text)
    old_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default={}, server_default="{}")
    changed_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        default={},
        server_default="{}",
    )
    transaction_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey(Transaction.id))


def render_sql(name: str) -> str:
    """Return the `audit_sql/` file `name` with the audit schema substituted in."""
    # `Template` treats `$$` as an escaped `$`, so double them to keep PL/pgSQL `$$` quoting.
    source = (AUDIT_SQL_DIR / name).read_text().replace("$$", "$$$$")
    return Template(source).substitute(schema=AUDIT_SCHEMA)


# --- What gets audited (the single source of truth) ------------------------------------------
#
# We audit each table's web-editable settings columns — the same ones moderators can change —
# plus the primary key, so every recorded change can be tied back to a specific guild/channel.
#
# To change what is audited:
#   * To audit a column moderators *can* edit: mark it `web_editable(...)` on the model
#     (`models/channel.py` / `models/guild.py`) — it is then audited automatically.
#   * To audit a column they *cannot* edit (e.g. an owner-only flag): add it to
#     `EXTRA_AUDITED_COLUMNS` below.
# Then add a migration whose `upgrade()` (and `downgrade()`) calls
# `audit.attach_triggers(op.get_bind())` to re-sync the triggers on existing databases — trigger
# attachment is idempotent, so this is safe to re-run.
AUDITED_MODELS: tuple[type, ...] = (Channel, Guild)

# Audited columns beyond each table's web-editable settings, keyed by table name.
EXTRA_AUDITED_COLUMNS: dict[str, set[str]] = {}


def audited_columns(model: Any) -> set[str]:
    """Column names audited on `model`: its web-editable settings, the PK, and any extras."""
    extra = EXTRA_AUDITED_COLUMNS.get(model.__tablename__, set())
    return set(web_editable_columns(model)) | {"xid"} | extra


def excluded_columns(model: Any) -> list[str]:
    """Columns the audit triggers ignore on `model` (everything that is not audited)."""
    audited = audited_columns(model)
    return sorted(c.name for c in model.__table__.columns if c.name not in audited)


def install(bind: Connection) -> None:
    """Create the audit schema, tables, trigger function, and JSONB operators (one-time)."""
    bind.execute(sa.text(render_sql("create_schema.sql")))
    # Transaction first; activity FKs it.
    for model in (Transaction, Activity):
        cast("sa.Table", model.__table__).create(bind)
    bind.execute(sa.text(render_sql("jsonb_change_key_name.sql")))
    bind.execute(sa.text(render_sql("create_activity.sql") + render_sql("audit_table.sql")))
    bind.execute(sa.text(render_sql("operators.sql")))


def attach_triggers(bind: Connection) -> None:
    """
    (Re)install the settings-audit triggers on the audited tables from the current models.

    Idempotent: the underlying `audit.audit_table(...)` drops and recreates the triggers, so this
    is safe to re-run from a migration whenever `audited_columns()` changes.
    """
    for model in AUDITED_MODELS:
        excludes = ", ".join(f"'{name}'" for name in excluded_columns(model))
        bind.execute(
            sa.text(
                f"SELECT {AUDIT_SCHEMA}.audit_table"
                f"('{model.__tablename__}'::regclass, ARRAY[{excludes}]::text[])",
            ),
        )


def uninstall(bind: Connection) -> None:
    """Detach the triggers and drop everything `install()` created."""
    for model in AUDITED_MODELS:
        for verb in ("insert", "update", "delete"):
            bind.execute(
                sa.text(f"DROP TRIGGER IF EXISTS audit_trigger_{verb} ON {model.__tablename__}"),
            )
    # Dropping the schema cascades to the audit tables and the trigger function.
    bind.execute(sa.text(f"DROP SCHEMA IF EXISTS {AUDIT_SCHEMA} CASCADE"))
    # The JSONB operator/helpers live in `public`, so drop them explicitly.
    bind.execute(sa.text("DROP OPERATOR IF EXISTS - (jsonb, jsonb)"))
    bind.execute(sa.text("DROP FUNCTION IF EXISTS jsonb_subtract(jsonb, jsonb)"))
    bind.execute(sa.text("DROP FUNCTION IF EXISTS get_setting(text, text)"))
    bind.execute(sa.text("DROP FUNCTION IF EXISTS jsonb_change_key_name(jsonb, text, text)"))


current_actor: contextvars.ContextVar[Actor | None] = contextvars.ContextVar(
    "spellbot_audit_actor",
    default=None,
)


@contextmanager
def actor(xid: int | None, name: str | None, source: str) -> Iterator[None]:
    """Attribute settings changes made within this context to the given actor."""
    token = current_actor.set(Actor(xid=xid, name=name, source=source))
    try:
        yield
    finally:
        current_actor.reset(token)


async def stamp() -> None:
    """
    Record the current actor for this DB transaction so the trigger can attribute its changes.

    Must run before the settings `UPDATE` in the same transaction: the audit trigger links each
    activity row to the `audit.transaction` row sharing `pg_current_xact_id()`. A no-op when no
    actor is in context (e.g. background tasks) — the change is still captured, just unattributed.
    """
    current = current_actor.get()
    if current is None:
        return
    await DatabaseSession.execute(
        pg_insert(Transaction)
        .values(
            actor_id=current.xid,
            actor_name=current.name,
            source=current.source,
            native_transaction_id=sa.func.pg_current_xact_id(),
            issued_at=sa.text("now() AT TIME ZONE 'UTC'"),
        )
        .on_conflict_do_nothing(constraint="transaction_unique_native_tx_id"),
    )


SETTINGS_CHANGE_PAGE_SIZE = 25


async def setting_changes(
    table_name: str,
    target_xid: int,
    *,
    page: int,
    page_size: int = SETTINGS_CHANGE_PAGE_SIZE,
) -> tuple[list[dict[str, Any]], int]:
    """
    Return one page of recorded settings changes for a guild or channel, newest first.

    Each entry is one save event with its actor and a per-field old/new diff. `table_name` is
    `"channels"` or `"guilds"`; `target_xid` is the row's `xid` (read from the audited JSON).
    Returns `(events, total)`.
    """
    base = (
        sa.select(
            Activity.id,
            Activity.issued_at,
            Activity.old_data,
            Activity.changed_data,
            Transaction.actor_id,
            Transaction.actor_name,
            Transaction.source,
        )
        .join(Transaction, Activity.transaction_id == Transaction.id, isouter=True)
        .where(
            Activity.table_name == table_name,
            Activity.verb == "update",
            Activity.old_data["xid"].astext == str(target_xid),
        )
    )
    total = (
        await DatabaseSession.execute(sa.select(sa.func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await DatabaseSession.execute(
            base.order_by(Activity.issued_at.desc(), Activity.id.desc())
            .offset(page * page_size)
            .limit(page_size),
        )
    ).all()
    events = [
        {
            "issued_at": row.issued_at,
            "actor_id": row.actor_id,
            "actor_name": row.actor_name,
            "source": row.source,
            "old_data": row.old_data or {},
            "changed_data": row.changed_data or {},
        }
        for row in rows
    ]
    return events, total


@asynccontextmanager
async def transaction() -> AsyncIterator[None]:
    """
    Run a settings change in one real DB transaction, stamped with the current actor.

    The audit trigger links each `audit.activity` row to the `audit.transaction` row sharing
    `pg_current_xact_id()`, so the stamp and the change must run in the same transaction. The
    app's engine uses AUTOCOMMIT isolation (each statement commits on its own), so we explicitly
    begin a READ COMMITTED transaction around the stamp and the caller's change.
    """
    # Close out any autobegun transaction so `begin()` can open a fresh, explicit one.
    await DatabaseSession.commit()
    async with DatabaseSession.begin():
        # Force a real (non-autocommit) transaction so the stamp and the change share an xid.
        await DatabaseSession.connection(execution_options={"isolation_level": "READ COMMITTED"})
        await stamp()
        yield
