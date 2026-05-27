"""add managed account proxies

Revision ID: 20260526_120000_add_managed_account_proxies
Revises: 20260513_000000_add_accounts_alias
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20260526_120000_add_managed_account_proxies"
down_revision = "20260513_000000_add_accounts_alias"
branch_labels = None
depends_on = None

_PROXY_TABLE = "account_proxies"
_PROXY_STATUS = sa.Enum("untested", "testing", "working", "failed", name="account_proxy_status")


def _columns(connection: Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(connection)
    if not inspector.has_table(table_name):
        return set()
    return {str(column["name"]) for column in inspector.get_columns(table_name) if column.get("name") is not None}


def _indexes(connection: Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(connection)
    if not inspector.has_table(table_name):
        return set()
    return {str(index["name"]) for index in inspector.get_indexes(table_name) if index.get("name") is not None}


def _foreign_keys(connection: Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(connection)
    if not inspector.has_table(table_name):
        return set()
    return {str(fk["name"]) for fk in inspector.get_foreign_keys(table_name) if fk.get("name") is not None}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_PROXY_TABLE):
        op.create_table(
            _PROXY_TABLE,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("display_name", sa.String(), nullable=False),
            sa.Column("proxy_url_encrypted", sa.LargeBinary(), nullable=False),
            sa.Column("status", _PROXY_STATUS, nullable=False, server_default="untested"),
            sa.Column("last_tested_at", sa.DateTime(), nullable=True),
            sa.Column("last_test_error", sa.Text(), nullable=True),
            sa.Column("last_test_latency_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if "idx_account_proxies_status" not in _indexes(bind, _PROXY_TABLE):
        op.create_index("idx_account_proxies_status", _PROXY_TABLE, ["status"], unique=False)

    if inspector.has_table("accounts"):
        account_columns = _columns(bind, "accounts")
        account_fks = _foreign_keys(bind, "accounts")
        if "proxy_id" not in account_columns:
            with op.batch_alter_table("accounts") as batch_op:
                batch_op.add_column(sa.Column("proxy_id", sa.String(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_accounts_proxy_id_account_proxies",
                    _PROXY_TABLE,
                    ["proxy_id"],
                    ["id"],
                    ondelete="RESTRICT",
                )
        elif "fk_accounts_proxy_id_account_proxies" not in account_fks:
            with op.batch_alter_table("accounts") as batch_op:
                batch_op.create_foreign_key(
                    "fk_accounts_proxy_id_account_proxies",
                    _PROXY_TABLE,
                    ["proxy_id"],
                    ["id"],
                    ondelete="RESTRICT",
                )
        if "idx_accounts_proxy_id" not in _indexes(bind, "accounts"):
            op.create_index("idx_accounts_proxy_id", "accounts", ["proxy_id"], unique=False)

    if inspector.has_table("http_bridge_sessions") and "proxy_fingerprint" not in _columns(
        bind, "http_bridge_sessions"
    ):
        with op.batch_alter_table("http_bridge_sessions") as batch_op:
            batch_op.add_column(sa.Column("proxy_fingerprint", sa.String(length=128), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("http_bridge_sessions") and "proxy_fingerprint" in _columns(bind, "http_bridge_sessions"):
        with op.batch_alter_table("http_bridge_sessions") as batch_op:
            batch_op.drop_column("proxy_fingerprint")

    if inspector.has_table("accounts"):
        if "idx_accounts_proxy_id" in _indexes(bind, "accounts"):
            op.drop_index("idx_accounts_proxy_id", table_name="accounts")
        if "proxy_id" in _columns(bind, "accounts"):
            with op.batch_alter_table("accounts") as batch_op:
                batch_op.drop_constraint("fk_accounts_proxy_id_account_proxies", type_="foreignkey")
                batch_op.drop_column("proxy_id")

    if inspector.has_table(_PROXY_TABLE):
        if "idx_account_proxies_status" in _indexes(bind, _PROXY_TABLE):
            op.drop_index("idx_account_proxies_status", table_name=_PROXY_TABLE)
        op.drop_table(_PROXY_TABLE)

    _PROXY_STATUS.drop(bind, checkfirst=True)
