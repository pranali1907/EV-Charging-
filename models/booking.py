from datetime import datetime
from enum import Enum

from sqlalchemy import Enum as SQLAlchemyEnum

from database.db import db


class BookingStatus(Enum):
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    CHARGING = "Charging"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    EXPIRED = "Expired"


class Booking(db.Model):
    """Reservation shell for a guest, station, and charger."""

    __tablename__ = "bookings"
    __table_args__ = (
        db.Index("ix_bookings_guest_status", "guest_id", "booking_status"),
        db.Index("ix_bookings_station_date", "station_id", "booking_date"),
        db.Index(
            "ix_bookings_charger_date_time",
            "charger_id",
            "booking_date",
            "booking_time",
        ),
    )

    booking_id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(
        db.Integer,
        db.ForeignKey("guest_users.guest_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    station_id = db.Column(
        db.Integer,
        db.ForeignKey("stations.station_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    charger_id = db.Column(
        db.Integer,
        db.ForeignKey("chargers.charger_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    connector_id = db.Column(
        db.Integer,
        db.ForeignKey("connector_types.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    user_mobile = db.Column(db.String(20), nullable=False)
    booking_date = db.Column(db.Date, nullable=False, index=True)
    booking_time = db.Column(db.Time, nullable=False)
    booking_start_time = db.Column(db.Time, nullable=False)
    booking_end_time = db.Column(db.Time, nullable=False)
    booking_status = db.Column(
        SQLAlchemyEnum(
            BookingStatus,
            name="booking_status_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=BookingStatus.PENDING,
        index=True,
    )
    booking_token_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    guest_user = db.relationship("GuestUser", back_populates="bookings")
    station = db.relationship("Station", back_populates="bookings")
    charger = db.relationship("Charger", back_populates="bookings")
    connector = db.relationship("ConnectorType")
    charging_session = db.relationship(
        "ChargingSession",
        back_populates="booking",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    payment = db.relationship(
        "Payment",
        back_populates="booking",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    def __repr__(self):
        return f"<Booking {self.booking_id}: {self.booking_status.value}>"

    def to_dict(self):
        return {
            "booking_id": self.booking_id,
            "guest_id": self.guest_id,
            "station_id": self.station_id,
            "charger_id": self.charger_id,
            "connector_id": self.connector_id,
            "user_mobile": self.user_mobile,
            "booking_date": (
                self.booking_date.isoformat() if self.booking_date else None
            ),
            "booking_time": (
                self.booking_time.isoformat() if self.booking_time else None
            ),
            "booking_start_time": (
                self.booking_start_time.isoformat() if self.booking_start_time else None
            ),
            "booking_end_time": (
                self.booking_end_time.isoformat() if self.booking_end_time else None
            ),
            "booking_status": (
                self.booking_status.value if self.booking_status else None
            ),
            "booking_token_amount": (
                float(self.booking_token_amount)
                if self.booking_token_amount is not None
                else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
