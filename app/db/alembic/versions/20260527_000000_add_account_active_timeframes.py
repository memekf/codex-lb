"""add account active timeframes

Revision ID: 20260527_000000_add_account_active_timeframes
Revises: 20260525_000000_add_usage_raw_window_latest_index, 20260526_120000_add_managed_account_proxies
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20260527_000000_add_account_active_timeframes"
down_revision = (
    "20260525_000000_add_usage_raw_window_latest_index",
    "20260526_120000_add_managed_account_proxies",
)
branch_labels = None
depends_on = None

_TIMEFRAME_TABLE = "account_active_timeframes"
_TIMEFRAME_MODE = sa.Enum(
    "fixed_weekdays",
    "random_weekly_days",
    name="account_active_timeframe_mode",
)


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

    if not inspector.has_table(_TIMEFRAME_TABLE):
        op.create_table(
            _TIMEFRAME_TABLE,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("display_name", sa.String(), nullable=False),
            sa.Column("timezone", sa.String(), nullable=False),
            sa.Column("start_minute", sa.Integer(), nullable=False),
            sa.Column("end_minute", sa.Integer(), nullable=False),
            sa.Column("mode", _TIMEFRAME_MODE, nullable=False),
            sa.Column("weekdays", sa.Text(), nullable=True),
            sa.Column("random_days_per_week", sa.Integer(), nullable=True),
            sa.Column("random_seed", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if "idx_account_active_timeframes_mode" not in _indexes(bind, _TIMEFRAME_TABLE):
        op.create_index("idx_account_active_timeframes_mode", _TIMEFRAME_TABLE, ["mode"], unique=False)

    if inspector.has_table("accounts"):
        account_columns = _columns(bind, "accounts")
        account_fks = _foreign_keys(bind, "accounts")
        if "active_timeframe_id" not in account_columns:
            with op.batch_alter_table("accounts") as batch_op:
                batch_op.add_column(sa.Column("active_timeframe_id", sa.String(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_accounts_active_timeframe_id_account_active_timeframes",
                    _TIMEFRAME_TABLE,
                    ["active_timeframe_id"],
                    ["id"],
                    ondelete="RESTRICT",
                )
        elif "fk_accounts_active_timeframe_id_account_active_timeframes" not in account_fks:
            with op.batch_alter_table("accounts") as batch_op:
                batch_op.create_foreign_key(
                    "fk_accounts_active_timeframe_id_account_active_timeframes",
                    _TIMEFRAME_TABLE,
                    ["active_timeframe_id"],
                    ["id"],
                    ondelete="RESTRICT",
                )
        if "idx_accounts_active_timeframe_id" not in _indexes(bind, "accounts"):
            op.create_index("idx_accounts_active_timeframe_id", "accounts", ["active_timeframe_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("accounts"):
        if "idx_accounts_active_timeframe_id" in _indexes(bind, "accounts"):
            op.drop_index("idx_accounts_active_timeframe_id", table_name="accounts")
        if "active_timeframe_id" in _columns(bind, "accounts"):
            with op.batch_alter_table("accounts") as batch_op:
                batch_op.drop_constraint(
                    "fk_accounts_active_timeframe_id_account_active_timeframes",
                    type_="foreignkey",
                )
                batch_op.drop_column("active_timeframe_id")

    if inspector.has_table(_TIMEFRAME_TABLE):
        if "idx_account_active_timeframes_mode" in _indexes(bind, _TIMEFRAME_TABLE):
            op.drop_index("idx_account_active_timeframes_mode", table_name=_TIMEFRAME_TABLE)
        op.drop_table(_TIMEFRAME_TABLE)

    _TIMEFRAME_MODE.drop(bind, checkfirst=True)
