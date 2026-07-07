"""Remove station name unique constraint

Revision ID: d4e6f8a1b2c3
Revises: 9b7a2c4d1e5f
Create Date: 2026-06-29 00:00:00.000000

"""
from alembic import op


revision = "d4e6f8a1b2c3"
down_revision = "9b7a2c4d1e5f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.drop_constraint("uq_station_name_city", type_="unique")


def downgrade():
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_station_name_city",
            ["station_name", "city"],
        )
