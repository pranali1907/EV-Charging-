from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from models.payment import Payment


def create_payment(data):
    try:
        payment = Payment(**data)
        db.session.add(payment)
        db.session.commit()
        return payment
    except SQLAlchemyError:
        db.session.rollback()
        return None


def get_payment(payment_id):
    try:
        return db.session.get(Payment, payment_id)
    except (TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        return None
