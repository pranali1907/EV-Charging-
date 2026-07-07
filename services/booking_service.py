from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from models.booking import Booking


def create_booking(data):
    try:
        booking = Booking(**data)
        db.session.add(booking)
        db.session.commit()
        return booking
    except SQLAlchemyError:
        db.session.rollback()
        return None


def get_booking(booking_id):
    try:
        return db.session.get(Booking, booking_id)
    except (TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        return None
