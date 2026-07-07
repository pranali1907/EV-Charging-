from datetime import datetime

from database.db import db


class Station(db.Model):
    """Charging station location and operating details."""

    __tablename__ = "stations"
    __table_args__ = (
        db.Index("ix_stations_city_status", "city", "status"),
        db.Index("ix_stations_address_lookup", "address"),
    )

    station_id = db.Column(db.Integer, primary_key=True)
    station_name = db.Column(db.String(150), nullable=False, index=True)
    city = db.Column(db.String(100), nullable=False, index=True)
    address = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    display_name = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    price_per_kwh = db.Column(db.Numeric(10, 2), nullable=False)
    is_open_24_hours = db.Column(db.Boolean, nullable=False, default=False)
    opening_time = db.Column(db.Time, nullable=False)
    closing_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(30), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    chargers = db.relationship(
        "Charger",
        back_populates="station",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    bookings = db.relationship("Booking", back_populates="station")

    def __repr__(self):
        return f"<Station {self.station_id}: {self.station_name}>"

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "station_name": self.station_name,
            "city": self.city,
            "address": self.address,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "display_name": self.display_name,
            "description": self.description,
            "image_url": self.image_url,
            "price_per_kwh": (
                float(self.price_per_kwh)
                if self.price_per_kwh is not None
                else None
            ),
            "is_open_24_hours": self.is_open_24_hours,
            "opening_time": (
                self.opening_time.isoformat() if self.opening_time else None
            ),
            "closing_time": (
                self.closing_time.isoformat() if self.closing_time else None
            ),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
