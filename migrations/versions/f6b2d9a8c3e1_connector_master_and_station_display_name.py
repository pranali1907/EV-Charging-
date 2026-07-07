"""Add connector master and station display name

Revision ID: f6b2d9a8c3e1
Revises: e5a9c1d7b4f2
Create Date: 2026-06-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f6b2d9a8c3e1"
down_revision = "e5a9c1d7b4f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "connector_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connector_name", sa.String(length=80), nullable=False),
        sa.Column("vehicle_type", sa.String(length=30), nullable=False),
        sa.Column("default_power_kw", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("is_standard", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector_name", name="uq_connector_types_name"),
    )

    with op.batch_alter_table("connector_types", schema=None) as batch_op:
        batch_op.create_index(
            "ix_connector_types_active_name",
            ["is_active", "connector_name"],
            unique=False,
        )

    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(length=500), nullable=True))

    with op.batch_alter_table("chargers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("connector_type_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_chargers_connector_type_id"),
            ["connector_type_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_chargers_connector_type_id_connector_types",
            "connector_types",
            ["connector_type_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.execute(
        """
        INSERT INTO connector_types
            (connector_name, vehicle_type, default_power_kw, is_standard, is_active, created_at, updated_at)
        SELECT connector_name, vehicle_type, default_power_kw, true, true, NOW(), NOW()
        FROM (
            VALUES
                ('CCS2', 'Car', 60.00),
                ('Type-2', 'Car', 22.00),
                ('LECCS', 'Bike', 3.30),
                ('15A AC Socket', 'Car + Bike', 3.30)
        ) AS defaults(connector_name, vehicle_type, default_power_kw)
        WHERE NOT EXISTS (SELECT 1 FROM connector_types)
        """
    )

    op.execute(
        """
        UPDATE chargers
        SET connector_type_id = connector_types.id
        FROM connector_types
        WHERE chargers.connector_type = connector_types.connector_name
        """
    )


def downgrade():
    with op.batch_alter_table("chargers", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_chargers_connector_type_id_connector_types",
            type_="foreignkey",
        )
        batch_op.drop_index(batch_op.f("ix_chargers_connector_type_id"))
        batch_op.drop_column("connector_type_id")

    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.drop_column("display_name")

    with op.batch_alter_table("connector_types", schema=None) as batch_op:
        batch_op.drop_index("ix_connector_types_active_name")

    op.drop_table("connector_types")
