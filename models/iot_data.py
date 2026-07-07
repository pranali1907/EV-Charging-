from datetime import datetime

from sqlalchemy import Enum as SQLAlchemyEnum

from database.db import db
from models.charger import ChargerStatus


class IoTData(db.Model):
    """Raw charger telemetry snapshots."""

    __tablename__ = "iot_data"
    __table_args__ = (
        db.Index("ix_iot_data_charger_last_updated", "charger_id", "last_updated"),
    )

    iot_id = db.Column(db.Integer, primary_key=True)
    charger_id = db.Column(
        db.Integer,
        db.ForeignKey("chargers.charger_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current = db.Column(db.Numeric(10, 2), nullable=False)
    voltage = db.Column(db.Numeric(10, 2), nullable=False)
    power = db.Column(db.Numeric(10, 2), nullable=False)
    temperature = db.Column(db.Numeric(6, 2), nullable=False)
    charger_status = db.Column(
        SQLAlchemyEnum(
            ChargerStatus,
            name="charger_status_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        index=True,
    )
    last_updated = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    charger = db.relationship("Charger", back_populates="iot_records")

    def __repr__(self):
        return f"<IoTData {self.iot_id}: charger {self.charger_id}>"

    def to_dict(self):
        return {
            "iot_id": self.iot_id,
            "charger_id": self.charger_id,
            "current": float(self.current) if self.current is not None else None,
            "voltage": float(self.voltage) if self.voltage is not None else None,
            "power": float(self.power) if self.power is not None else None,
            "temperature": (
                float(self.temperature) if self.temperature is not None else None
            ),
            "charger_status": (
                self.charger_status.value if self.charger_status else None
            ),
            "last_updated": (
                self.last_updated.isoformat() if self.last_updated else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
