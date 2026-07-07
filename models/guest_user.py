from datetime import datetime

from database.db import db


class GuestUser(db.Model):
    """Non-login guest customer details for future OTP verification."""

    __tablename__ = "guest_users"
    __table_args__ = (
        db.Index("ix_guest_users_mobile_vehicle", "mobile_number", "vehicle_number"),
    )

    guest_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    mobile_number = db.Column(db.String(20), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), nullable=True, unique=True, index=True)
    vehicle_number = db.Column(db.String(30), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    bookings = db.relationship("Booking", back_populates="guest_user")

    def __repr__(self):
        return f"<GuestUser {self.guest_id}: {self.mobile_number}>"

    def to_dict(self):
        return {
            "guest_id": self.guest_id,
            "full_name": self.full_name,
            "mobile_number": self.mobile_number,
            "email": self.email,
            "vehicle_number": self.vehicle_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
