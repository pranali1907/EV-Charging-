from datetime import datetime
from enum import Enum

from sqlalchemy import Enum as SQLAlchemyEnum

from database.db import db


class ChargerStatus(Enum):
    AVAILABLE = "Available"
    BUSY = "Busy"
    OFFLINE = "Offline"
    MAINTENANCE = "Maintenance"


class VehicleType(Enum):
    CAR = "Car"
    BIKE = "Bike"
    CAR_BIKE = "Car + Bike"


class Charger(db.Model):
    """Physical charging point installed at a station."""

    __tablename__ = "chargers"
    __table_args__ = (
        db.UniqueConstraint(
            "station_id",
            "charger_name",
            name="uq_charger_station_name",
        ),
        db.Index("ix_chargers_station_status", "station_id", "status"),
    )

    charger_id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(
        db.Integer,
        db.ForeignKey("stations.station_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    charger_name = db.Column(db.String(120), nullable=False)
    connector_type_id = db.Column(
        db.Integer,
        db.ForeignKey("connector_types.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    connector_type = db.Column(db.String(50), nullable=False, index=True)
    power_kw = db.Column(db.Numeric(7, 2), nullable=False)
    vehicle_type = db.Column(db.String(30), nullable=False, index=True)
    status = db.Column(
        SQLAlchemyEnum(
            ChargerStatus,
            name="charger_status_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=ChargerStatus.AVAILABLE,
        index=True,
    )
    iot_enabled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    station = db.relationship("Station", back_populates="chargers")
    connector = db.relationship("ConnectorType", back_populates="chargers")
    bookings = db.relationship("Booking", back_populates="charger")
    iot_records = db.relationship(
        "IoTData",
        back_populates="charger",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Charger {self.charger_id}: {self.charger_name}>"

    def to_dict(self):
        return {
            "charger_id": self.charger_id,
            "station_id": self.station_id,
            "charger_name": self.charger_name,
            "connector_type": self.connector_type,
            "power_kw": float(self.power_kw) if self.power_kw is not None else None,
            "vehicle_type": self.vehicle_type,
            "status": self.status.value if self.status else None,
            "iot_enabled": self.iot_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
