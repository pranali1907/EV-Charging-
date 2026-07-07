"""Drop unique station coordinates constraint

Revision ID: drop_unique_station_coordinates
Revises: a7c9e2f4b6d8
Create Date: 2026-07-05 00:00:00.000000
"""
from alembic import op

revision = "drop_unique_station_coordinates"
down_revision = "a7c9e2f4b6d8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.drop_constraint("uq_stations_coordinates", type_="unique")
        batch_op.create_index(
            "ix_stations_coordinates_lookup",
            ["latitude", "longitude"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.drop_index("ix_stations_coordinates_lookup")
        batch_op.create_unique_constraint(
            "uq_stations_coordinates",
            ["latitude", "longitude"],
        )
