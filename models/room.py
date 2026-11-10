
from extensions import db


class Room(db.Model):
    """Base room class."""

    __tablename__ = "rooms"

    __table_args__ = (
        db.CheckConstraint(
            "price_per_night > 0",
            name="ck_rooms_price"
        ),
        db.CheckConstraint(
            "capacity > 0",
            name="ck_rooms_capacity"
        ),
        db.CheckConstraint(
            "room_type IN ('Single','Double','Suite')",
            name="ck_rooms_type"
        ),
        db.CheckConstraint(
            "status IN ('Available','Maintenance')",
            name="ck_rooms_status"
        ),
    )

    room_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    room_type = db.Column(db.String(20), nullable=False)
    price_per_night = db.Column(
        db.Numeric(10, 2, asdecimal=False),
        nullable=False
    )
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Available"
    )
    amenities = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)

    bookings = db.relationship("Booking", back_populates="room")

    __mapper_args__ = {
        "polymorphic_on": room_type
    }

    def calculate_price(self, nights):
        """Calculate the total room price."""
        return round(self.price_per_night * nights, 2)

    @property
    def amenity_list(self):
        return [
            item.strip()
            for item in (self.amenities or "").split(",")
            if item.strip()
        ]

    @property
    def is_bookable(self):
        return self.status == "Available"

    def __repr__(self):
        return f"<{self.room_type} Room {self.room_number}>"


class SingleRoom(Room):
    """Single occupancy room."""

    __mapper_args__ = {
        "polymorphic_identity": "Single"
    }


class DoubleRoom(Room):
    """Double occupancy room."""

    __mapper_args__ = {
        "polymorphic_identity": "Double"
    }


class Suite(Room):
    """Premium room with a long-stay discount."""

    __mapper_args__ = {
        "polymorphic_identity": "Suite"
    }

    def calculate_price(self, nights):
        total = self.price_per_night * nights

        if nights >= 5:
            total *= 0.90

        return round(total, 2)
