"""Add station validation indexes

Revision ID: e5a9c1d7b4f2
Revises: d4e6f8a1b2c3
Create Date: 2026-06-30 00:00:00.000000

"""
from alembic import op


revision = "e5a9c1d7b4f2"
down_revision = "d4e6f8a1b2c3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE stations DROP CONSTRAINT IF EXISTS uq_station_name_city")

    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_stations_address_lookup",
            ["address"],
            unique=False,
        )
        batch_op.create_index(
            "ix_stations_coordinates_lookup",
            ["latitude", "longitude"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.drop_index("ix_stations_coordinates_lookup")
        batch_op.drop_index("ix_stations_address_lookup")
