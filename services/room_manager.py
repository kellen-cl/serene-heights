import math
import re

from sqlalchemy import func

from extensions import db
from models import DoubleRoom, Room, SingleRoom, Suite

ROOM_CLASSES = {"Single": SingleRoom, "Double": DoubleRoom, "Suite": Suite}
NUMBER_RE = re.compile(r"^[A-Za-z0-9-]{1,10}$")


class RoomManager:
    """Add, edit and delete rooms with validation."""
    TYPES = tuple(ROOM_CLASSES)
    STATUSES = ("Available", "Maintenance")

    @classmethod
    def _validate(cls, data, room_id=None):
        """Returns (clean_fields, errors)."""
        errors = []

        number = data.get("room_number", "").strip()
        if not NUMBER_RE.match(number):
            errors.append("Room number must be 1-10 characters: letters, numbers or hyphens.")
        elif Room.query.filter(
            func.lower(Room.room_number) == number.lower(), Room.room_id != (room_id or 0)
        ).first():
            errors.append(f"Room {number} already exists.")

        price = None
        try:
            price = round(float(data.get("price_per_night", "")), 2)
            if not math.isfinite(price) or price <= 0 or price > 100000:
                raise ValueError
        except ValueError:
            errors.append("Price per night must be a number greater than zero.")

        capacity = None
        try:
            capacity = int(data.get("capacity", ""))
            if capacity < 1 or capacity > 10:
                raise ValueError
        except ValueError:
            errors.append("Capacity must be a whole number between 1 and 10.")

        status = data.get("status", "Available")
        if status not in cls.STATUSES:
            errors.append("Status must be Available or Maintenance.")

        amenities = data.get("amenities", "").strip()
        description = data.get("description", "").strip()
        if len(amenities) > 500:
            errors.append("Amenities cannot exceed 500 characters.")
        if len(description) > 1000:
            errors.append("Description cannot exceed 1000 characters.")

        clean = {
            "room_number": number, "price_per_night": price, "capacity": capacity,
            "status": status, "amenities": amenities or None, "description": description or None,
        }
        return clean, errors

    @classmethod
    def create(cls, data):
        """Returns (room, errors)."""
        clean, errors = cls._validate(data)
        room_type = data.get("room_type", "")
        if room_type not in ROOM_CLASSES:
            errors.append("Choose a valid room type.")
        if errors:
            return None, errors

        room = ROOM_CLASSES[room_type](**clean)  # polymorphism: subclass sets room_type
        db.session.add(room)
        db.session.commit()
        return room, []

    @classmethod
    def update(cls, room, data):
        """Returns a list of errors (empty list means saved). Room type is not changed."""
        clean, errors = cls._validate(data, room_id=room.room_id)
        if errors:
            return errors
        for field, value in clean.items():
            setattr(room, field, value)
        db.session.commit()
        return []

    @staticmethod
    def delete(room):
        """Returns an error message, or None when deleted."""
        if room.bookings:
            return (f"Room {room.room_number} has booking history and cannot be deleted. "
                    "Set it to Maintenance instead.")
        db.session.delete(room)
        db.session.commit()
        return None