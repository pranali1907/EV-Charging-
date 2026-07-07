"""Refactor station charger architecture

Revision ID: 9b7a2c4d1e5f
Revises: 0d91801a96b7
Create Date: 2026-06-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "9b7a2c4d1e5f"
down_revision = "0d91801a96b7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_open_24_hours",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.drop_column("supported_vehicles")
        batch_op.drop_column("supported_connectors")
        batch_op.alter_column("is_open_24_hours", server_default=None)

    with op.batch_alter_table("chargers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "vehicle_type",
                sa.String(length=30),
                server_default="Car",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "iot_enabled",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_chargers_vehicle_type"),
            ["vehicle_type"],
            unique=False,
        )
        batch_op.alter_column("vehicle_type", server_default=None)
        batch_op.alter_column("iot_enabled", server_default=None)


def downgrade():
    with op.batch_alter_table("chargers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chargers_vehicle_type"))
        batch_op.drop_column("iot_enabled")
        batch_op.drop_column("vehicle_type")

    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "supported_connectors",
                sa.JSON(),
                server_default=sa.text("'[]'::json"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "supported_vehicles",
                sa.JSON(),
                server_default=sa.text("'[]'::json"),
                nullable=False,
            )
        )
        batch_op.drop_column("is_open_24_hours")
        batch_op.alter_column("supported_connectors", server_default=None)
        batch_op.alter_column("supported_vehicles", server_default=None)
