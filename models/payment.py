
from extensions import db


class Payment(db.Model):
    """Stores payment information for hotel bookings."""

    __tablename__ = "payments"

    __table_args__ = (
        db.CheckConstraint(
            "amount >= 0",
            name="ck_payments_amount"
        ),
        db.CheckConstraint(
            "method IN ('Cash','Card','Mobile Money')",
            name="ck_payments_method"
        ),
        db.CheckConstraint(
            "status IN ('Pending','Paid','Refunded')",
            name="ck_payments_status"
        ),
    )

    payment_id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    booking_id = db.Column(
        db.Integer,
        db.ForeignKey("bookings.booking_id"),
        unique=True,
        nullable=False
    )

    processed_by = db.Column(
        db.Integer,
        db.ForeignKey("staff.staff_id"),
        nullable=True
    )

    amount = db.Column(
        db.Numeric(10, 2, asdecimal=False),
        nullable=False
    )

    method = db.Column(db.String(20), nullable=False)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending"
    )

    payment_date = db.Column(db.Date, nullable=True)

    booking = db.relationship(
        "Booking",
        back_populates="payment"
    )

    processor = db.relationship(
        "Staff",
        back_populates="payments_processed"
    )

    def __repr__(self):
        return f"<Payment {self.payment_id} {self.status}>"
