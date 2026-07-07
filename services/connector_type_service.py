from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database.db import db
from models.charger import Charger
from models.connector_type import ConnectorType


VALID_VEHICLE_TYPES = {"Car", "Bike", "Car + Bike"}
DEFAULT_CONNECTORS = [
    {
        "connector_name": "CCS2",
        "vehicle_type": "Car",
        "default_power_kw": Decimal("60.00"),
        "is_standard": True,
    },
    {
        "connector_name": "Type-2",
        "vehicle_type": "Car",
        "default_power_kw": Decimal("22.00"),
        "is_standard": True,
    },
    {
        "connector_name": "LECCS",
        "vehicle_type": "Bike",
        "default_power_kw": Decimal("3.30"),
        "is_standard": True,
    },
    {
        "connector_name": "15A AC Socket",
        "vehicle_type": "Car + Bike",
        "default_power_kw": Decimal("3.30"),
        "is_standard": True,
    },
    {
        "connector_name": "CCS2 DC Fast Charger",
        "vehicle_type": "Car",
        "default_power_kw": Decimal("120.00"),
        "is_standard": True,
    },
]


def seed_default_connectors():
    try:
        for connector_data in DEFAULT_CONNECTORS:
            exists = ConnectorType.query.filter(
                db.func.lower(ConnectorType.connector_name)
                == connector_data["connector_name"].lower()
            ).first()
            if not exists:
                db.session.add(ConnectorType(**connector_data))

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def get_all_connector_types(include_inactive=True):
    try:
        query = ConnectorType.query

        if not include_inactive:
            query = query.filter(ConnectorType.is_active.is_(True))

        return query.order_by(ConnectorType.connector_name).all()
    except SQLAlchemyError:
        db.session.rollback()
        return []


def get_active_connector_types():
    return get_all_connector_types(include_inactive=False)


def get_connector_type(connector_id):
    try:
        if connector_id is None:
            return None

        return db.session.get(ConnectorType, connector_id)
    except (TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        return None


def connector_name_exists(connector_name, current_connector_id=None):
    try:
        query = ConnectorType.query.filter(
            db.func.lower(ConnectorType.connector_name)
            == (connector_name or "").strip().lower()
        )

        if current_connector_id:
            query = query.filter(ConnectorType.id != current_connector_id)

        return query.first() is not None
    except SQLAlchemyError:
        db.session.rollback()
        return True


def create_connector_type(data):
    try:
        connector = ConnectorType(**data)
        db.session.add(connector)
        db.session.commit()
        return connector
    except (IntegrityError, SQLAlchemyError):
        db.session.rollback()
        return None


def update_connector_type(connector_id, data):
    connector = get_connector_type(connector_id)

    if connector is None:
        return None

    try:
        for key, value in data.items():
            if hasattr(connector, key):
                setattr(connector, key, value)

        Charger.query.filter(Charger.connector_type_id == connector.id).update(
            {
                "connector_type": connector.connector_name,
                "vehicle_type": connector.vehicle_type,
            },
            synchronize_session=False,
        )

        db.session.commit()
        return connector
    except (IntegrityError, SQLAlchemyError):
        db.session.rollback()
        return None


def delete_connector_type(connector_id):
    connector = get_connector_type(connector_id)

    if connector is None:
        return False, "Connector type not found."

    if connector.chargers:
        return False, "Connector type cannot be deleted because chargers use it."

    try:
        db.session.delete(connector)
        db.session.commit()
        return True, "Connector type deleted successfully."
    except SQLAlchemyError:
        db.session.rollback()
        return False, "Connector type could not be deleted."


def connector_to_admin_dict(connector):
    return {
        "id": connector.id,
        "connector_name": connector.connector_name,
        "vehicle_type": connector.vehicle_type,
        "default_power_kw": (
            float(connector.default_power_kw)
            if connector.default_power_kw is not None
            else 0
        ),
        "is_standard": connector.is_standard,
        "is_active": connector.is_active,
        "updated_at": (
            connector.updated_at.strftime("%d %b %Y, %I:%M %p")
            if connector.updated_at
            else ""
        ),
    }


def parse_power(value):
    try:
        return Decimal((value or "").strip())
    except (InvalidOperation, AttributeError):
        return None
