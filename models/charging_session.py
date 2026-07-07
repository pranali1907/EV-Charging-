from datetime import datetime

from database.db import db


class ChargingSession(db.Model):
    """Metered charging result for a completed booking."""

    __tablename__ = "charging_sessions"

    session_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(
        db.Integer,
        db.ForeignKey("bookings.booking_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    units_consumed = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    charging_duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    energy_cost = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    gst_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    booking_token_adjustment = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    final_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    booking = db.relationship("Booking", back_populates="charging_session")

    def __repr__(self):
        return f"<ChargingSession {self.session_id}: booking {self.booking_id}>"

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "booking_id": self.booking_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "units_consumed": (
                float(self.units_consumed)
                if self.units_consumed is not None
                else None
            ),
            "charging_duration_minutes": self.charging_duration_minutes,
            "energy_cost": (
                float(self.energy_cost) if self.energy_cost is not None else None
            ),
            "gst_amount": (
                float(self.gst_amount) if self.gst_amount is not None else None
            ),
            "booking_token_adjustment": (
                float(self.booking_token_adjustment)
                if self.booking_token_adjustment is not None
                else None
            ),
            "final_amount": (
                float(self.final_amount) if self.final_amount is not None else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
