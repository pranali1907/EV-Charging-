from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from models.guest_user import GuestUser


def get_guest_by_mobile(mobile_number):
    try:
        mobile_number = (mobile_number or "").strip()

        if not mobile_number:
            return None

        return GuestUser.query.filter_by(mobile_number=mobile_number).first()
    except SQLAlchemyError:
        db.session.rollback()
        return None


def create_guest(data):
    try:
        existing_guest = get_guest_by_mobile(data.get("mobile_number"))

        if existing_guest:
            return existing_guest

        guest = GuestUser(**data)
        db.session.add(guest)
        db.session.commit()
        return guest
    except SQLAlchemyError:
        db.session.rollback()
        return None


def get_guest(guest_id):
    try:
        return db.session.get(GuestUser, guest_id)
    except (TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        return None


def verify_guest(mobile_number):
    mobile_number = (mobile_number or "").strip()
    guest = get_guest_by_mobile(mobile_number)

    if guest:
        return guest

    guest_data = {
        "full_name": "Guest User",
        "mobile_number": mobile_number,
        "email": None,
        "vehicle_number": f"GUEST-{mobile_number[-4:]}",
    }

    return create_guest(guest_data)
