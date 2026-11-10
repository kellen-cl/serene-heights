
from datetime import datetime

from extensions import db


BOOKING_STATUSES = (
    "Pending",
    "Confirmed",
    "Checked-In",
    "Completed",
    "Cancelled"
)


class Booking(db.Model):
    """Represents a hotel room reservation."""

    __tablename__ = "bookings"

    __table_args__ = (
        db.CheckConstraint(
            "check_out > check_in",
            name="ck_bookings_dates"
        ),
        db.CheckConstraint(
            "num_guests > 0",
            name="ck_bookings_guests"
        ),
        db.CheckConstraint(
            "total_amount >= 0",
            name="ck_bookings_total"
        ),
        db.CheckConstraint(
            "status IN ('Pending','Confirmed','Checked-In','Completed','Cancelled')",
            name="ck_bookings_status"
        ),
    )

    booking_id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    guest_id = db.Column(
        db.Integer,
        db.ForeignKey("guests.guest_id"),
        nullable=False
    )

    room_id = db.Column(
        db.Integer,
        db.ForeignKey("rooms.room_id"),
        nullable=False
    )

    handled_by = db.Column(
        db.Integer,
        db.ForeignKey("staff.staff_id"),
        nullable=True
    )

    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)

    num_guests = db.Column(db.Integer, nullable=False)

    total_amount = db.Column(
        db.Numeric(10, 2, asdecimal=False),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now
    )

    guest = db.relationship(
        "Guest",
        back_populates="bookings"
    )

    room = db.relationship(
        "Room",
        back_populates="bookings"
    )

    handler = db.relationship(
        "Staff",
        back_populates="bookings_handled"
    )

    payment = db.relationship(
        "Payment",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan"
    )

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    @property
    def reference(self):
        return f"BK-{self.booking_id:04d}"

    @property
    def is_cancellable(self):
        return self.status in ("Pending", "Confirmed")

    def __repr__(self):
        return f"<Booking {self.reference} {self.status}>"
