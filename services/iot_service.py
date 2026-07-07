from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from models.iot_data import IoTData


def save_iot_data(data):
    try:
        iot_data = IoTData(**data)
        db.session.add(iot_data)
        db.session.commit()
        return iot_data
    except SQLAlchemyError:
        db.session.rollback()
        return None


def get_latest_iot_status(charger_id):
    try:
        return (
            IoTData.query.filter_by(charger_id=charger_id)
            .order_by(IoTData.last_updated.desc())
            .first()
        )
    except (TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        return None
