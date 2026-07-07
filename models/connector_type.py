from datetime import datetime

from database.db import db


class ConnectorType(db.Model):
    """Admin-managed connector master record."""

    __tablename__ = "connector_types"
    __table_args__ = (
        db.UniqueConstraint("connector_name", name="uq_connector_types_name"),
        db.Index("ix_connector_types_active_name", "is_active", "connector_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    connector_name = db.Column(db.String(80), nullable=False)
    vehicle_type = db.Column(db.String(30), nullable=False)
    default_power_kw = db.Column(db.Numeric(7, 2), nullable=False)
    is_standard = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    chargers = db.relationship("Charger", back_populates="connector")

    def __repr__(self):
        return f"<ConnectorType {self.id}: {self.connector_name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "connector_name": self.connector_name,
            "vehicle_type": self.vehicle_type,
            "default_power_kw": (
                float(self.default_power_kw)
                if self.default_power_kw is not None
                else None
            ),
            "is_standard": self.is_standard,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
