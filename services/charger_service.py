from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from models.charger import Charger, ChargerStatus
from models.station import Station


VALID_VEHICLE_TYPES = {"Car", "Bike", "Car + Bike"}
VALID_CHARGER_STATUSES = {status.value for status in ChargerStatus}


def get_all_chargers():
    """Return all chargers with station details."""
    try:
        return (
            Charger.query.join(Station)
            .order_by(Station.station_name, Charger.charger_name)
            .all()
        )
    except SQLAlchemyError:
        db.session.rollback()
        return []


def get_charger(charger_id):
    """Return one charger by primary key."""
    try:
        if charger_id is None:
            return None

        return db.session.get(Charger, charger_id)
    except (TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        return None


def search_chargers(search_query="", status_filter="All", connector_filter="All"):
    """Search and filter chargers for the admin charger list."""
    try:
        query = Charger.query.join(Station)
        search_query = (search_query or "").strip()
        status_filter = status_filter or "All"
        connector_filter = connector_filter or "All"

        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                db.or_(
                    Station.station_name.ilike(search_pattern),
                    Charger.charger_name.ilike(search_pattern),
                    Charger.connector_type.ilike(search_pattern),
                    Charger.vehicle_type.ilike(search_pattern),
                )
            )

        if status_filter in VALID_CHARGER_STATUSES:
            query = query.filter(Charger.status == ChargerStatus(status_filter))

        if connector_filter and connector_filter != "All":
            query = query.filter(Charger.connector_type == connector_filter)

        return query.order_by(Charger.charger_id.desc()).all()
    except SQLAlchemyError:
        db.session.rollback()
        return []


def create_charger(data):
    """Create a charger record."""
    try:
        charger = Charger(**data)
        db.session.add(charger)
        db.session.commit()
        return charger
    except SQLAlchemyError:
        db.session.rollback()
        return None


def update_charger(charger_id, data):
    """Update charger columns from a dictionary."""
    charger = get_charger(charger_id)

    if charger is None:
        return None

    try:
        for key, value in data.items():
            if hasattr(charger, key):
                setattr(charger, key, value)

        db.session.commit()
        return charger
    except SQLAlchemyError:
        db.session.rollback()
        return None


def delete_charger(charger_id):
    """Delete a charger when found."""
    charger = get_charger(charger_id)

    if charger is None:
        return False, "Charger not found."

    try:
        db.session.delete(charger)
        db.session.commit()
        return True, "Charger deleted successfully."
    except SQLAlchemyError:
        db.session.rollback()
        return False, "Charger could not be deleted."


def charger_name_exists(station_id, charger_name, current_charger_id=None):
    """Check duplicate charger names inside the same station."""
    try:
        query = Charger.query.filter(
            Charger.station_id == station_id,
            db.func.lower(Charger.charger_name) == charger_name.strip().lower(),
        )

        if current_charger_id:
            query = query.filter(Charger.charger_id != current_charger_id)

        return query.first() is not None
    except SQLAlchemyError:
        db.session.rollback()
        return True


def charger_to_admin_dict(charger):
    """Convert charger model for admin table rendering."""
    connector_name = (
        charger.connector.connector_name if charger.connector else charger.connector_type
    )
    vehicle_type = charger.connector.vehicle_type if charger.connector else charger.vehicle_type

    return {
        "charger_id": charger.charger_id,
        "station_id": charger.station_id,
        "station_name": charger.station.station_name if charger.station else "",
        "charger_name": charger.charger_name,
        "connector_type": connector_name,
        "power_kw": float(charger.power_kw) if charger.power_kw is not None else 0,
        "vehicle_type": vehicle_type,
        "status": charger.status.value if charger.status else "",
        "iot_enabled": charger.iot_enabled,
        "updated_at": (
            charger.updated_at.strftime("%d %b %Y, %I:%M %p")
            if charger.updated_at
            else ""
        ),
    }


def charger_to_public_dict(charger):
    """Convert a charger model for public station and booking pages."""
    connector_name = (
        charger.connector.connector_name if charger.connector else charger.connector_type
    )
    vehicle_type = charger.connector.vehicle_type if charger.connector else charger.vehicle_type

    return {
        "charger_id": charger.charger_id,
        "station_id": charger.station_id,
        "charger_name": charger.charger_name,
        "connector_type": connector_name,
        "power_kw": float(charger.power_kw) if charger.power_kw is not None else 0,
        "vehicle_type": vehicle_type,
        "status": charger.status.value if charger.status else "",
        "iot_enabled": charger.iot_enabled,
    }


def update_charger_statuses():
    """Automatically updates charger statuses based on current active bookings."""
    from datetime import datetime
    from models.booking import Booking, BookingStatus

    try:
        now = datetime.now()
        today = now.date()
        current_time = now.time()

        chargers = Charger.query.all()
        for charger in chargers:
            # Offline and Maintenance chargers are manually managed, do not override
            if charger.status in [ChargerStatus.OFFLINE, ChargerStatus.MAINTENANCE]:
                continue

            # Check if there is an active confirmed/charging booking right now
            active_booking = Booking.query.filter(
                Booking.charger_id == charger.charger_id,
                Booking.booking_date == today,
                Booking.booking_start_time <= current_time,
                Booking.booking_end_time >= current_time,
                Booking.booking_status.in_([BookingStatus.CONFIRMED, BookingStatus.CHARGING])
            ).first()

            target_status = ChargerStatus.BUSY if active_booking else ChargerStatus.AVAILABLE
            if charger.status != target_status:
                charger.status = target_status

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error updating charger statuses: {e}")
