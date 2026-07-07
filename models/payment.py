from datetime import datetime
from enum import Enum

from sqlalchemy import Enum as SQLAlchemyEnum

from database.db import db


class PaymentStatus(Enum):
    PENDING = "Pending"
    SUCCESS = "Success"
    FAILED = "Failed"
    REFUNDED = "Refunded"


class Payment(db.Model):
    """Payment record associated with exactly one booking."""

    __tablename__ = "payments"

    payment_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(
        db.Integer,
        db.ForeignKey("bookings.booking_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    payment_type = db.Column(db.String(50), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)
    transaction_id = db.Column(db.String(150), nullable=True, unique=True, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_status = db.Column(
        SQLAlchemyEnum(
            PaymentStatus,
            name="payment_status_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )
    payment_time = db.Column(db.DateTime, nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    booking = db.relationship("Booking", back_populates="payment")

    def __repr__(self):
        return f"<Payment {self.payment_id}: {self.payment_status.value}>"

    def to_dict(self):
        return {
            "payment_id": self.payment_id,
            "booking_id": self.booking_id,
            "payment_type": self.payment_type,
            "payment_method": self.payment_method,
            "transaction_id": self.transaction_id,
            "amount": float(self.amount) if self.amount is not None else None,
            "payment_status": (
                self.payment_status.value if self.payment_status else None
            ),
            "payment_time": (
                self.payment_time.isoformat() if self.payment_time else None
            ),
            "payment_date": (
                self.payment_date.isoformat() if self.payment_date else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
