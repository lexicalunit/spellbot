# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Stores API tokens as SHA-256 hashes instead of plaintext.

Each existing key is replaced with the hex SHA-256 of itself, so tokens already handed
out keep working: the server hashes the bearer token it receives and looks that up.
The plaintext can't be recovered, so a downgrade keeps the hashes and every token has
to be reissued afterwards.

Revision ID: cbeb61d4a042
Revises: 199051b060c8
Create Date: 2026-11-03 18:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "cbeb61d4a042"
down_revision = "199051b060c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("tokens", "key", new_column_name="key_hash")
    op.execute("UPDATE tokens SET key_hash = encode(sha256(convert_to(key_hash, 'UTF8')), 'hex')")
    op.drop_index("ix_tokens_key", table_name="tokens")
    op.create_index("ix_tokens_key_hash", "tokens", ["key_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tokens_key_hash", table_name="tokens")
    op.alter_column("tokens", "key_hash", new_column_name="key")
    op.create_index("ix_tokens_key", "tokens", ["key"], unique=False)
