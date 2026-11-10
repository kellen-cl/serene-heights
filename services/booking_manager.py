from datetime import date, datetime

from extensions import db
from models import Booking, Payment, Room


class BookingManager:
    """Availability search, the double-booking rule, and booking creation/cancellation.

    Two stays overlap when: new_check_in < existing_check_out
                        AND new_check_out > existing_check_in
    """
    ACTIVE_STATUSES = ("Pending", "Confirmed", "Checked-In")
    PAYMENT_METHODS = ("Cash", "Card", "Mobile Money")
    INSTANT_METHODS = ("Card", "Mobile Money")  # simulated: marked Paid immediately
    MAX_NIGHTS = 30
    MAX_GUESTS = 10

    @staticmethod
    def parse_date(value):
        try:
            return datetime.strptime(value or "", "%Y-%m-%d").date()
        except ValueError:
            return None

    @classmethod
    def validate_stay(cls, check_in, check_out, num_guests):
        """Returns (check_in, check_out, num_guests, errors)."""
        errors = []
        ci = cls.parse_date(check_in)
        co = cls.parse_date(check_out)

        if not ci or not co:
            errors.append("Please select valid check-in and check-out dates.")
        else:
            if ci < date.today():
                errors.append("Check-in cannot be in the past.")
            if co <= ci:
                errors.append("Check-out must be later than check-in.")
            elif (co - ci).days > cls.MAX_NIGHTS:
                errors.append(f"A single booking cannot exceed {cls.MAX_NIGHTS} nights.")

        try:
            guests = int(num_guests or 1)
            if guests < 1 or guests > cls.MAX_GUESTS:
                raise ValueError
        except ValueError:
            guests = 1
            errors.append(f"Number of guests must be between 1 and {cls.MAX_GUESTS}.")

        return ci, co, guests, errors

    @classmethod
    def _overlapping(cls, check_in, check_out):
        return Booking.query.filter(
            Booking.status.in_(cls.ACTIVE_STATUSES),
            Booking.check_in < check_out,
            Booking.check_out > check_in,
        )

    @classmethod
    def is_room_available(cls, room_id, check_in, check_out, exclude_booking_id=None):
        """True if no active booking overlaps these dates for this room."""
        q = cls._overlapping(check_in, check_out).filter(Booking.room_id == room_id)
        if exclude_booking_id:
            q = q.filter(Booking.booking_id != exclude_booking_id)
        return q.first() is None

    @classmethod
    def search_available(cls, check_in, check_out, num_guests, room_type=None):
        """Rooms that are not in Maintenance, fit the guests, and have no overlap."""
        booked_ids = [
            row[0] for row in
            cls._overlapping(check_in, check_out).with_entities(Booking.room_id).all()
        ]
        q = Room.query.filter(Room.status == "Available", Room.capacity >= num_guests)
        if room_type:
            q = q.filter(Room.room_type == room_type)
        if booked_ids:
            q = q.filter(~Room.room_id.in_(booked_ids))
        return q.order_by(Room.price_per_night, Room.room_number).all()

    # ---------- Create / cancel ----------
    @classmethod
    def create_booking(cls, guest, room, check_in, check_out, num_guests, method):
        """Returns (booking, errors). Creates the booking and its payment together."""
        ci, co, n, errors = cls.validate_stay(check_in, check_out, num_guests)
        if method not in cls.PAYMENT_METHODS:
            errors.append("Please choose a payment method.")
        if not room.is_bookable:
            errors.append("This room is currently unavailable.")
        elif n > room.capacity:
            errors.append(f"This room holds up to {room.capacity} guests.")
        if errors:
            return None, errors

        clash = "Sorry, this room has just been booked for those dates. Please choose another."
        if not cls.is_room_available(room.room_id, ci, co):
            return None, [clash]

        nights = (co - ci).days
        total = room.calculate_price(nights)
        paid_now = method in cls.INSTANT_METHODS

        booking = Booking(
            guest_id=guest.guest_id, room_id=room.room_id,
            check_in=ci, check_out=co, num_guests=n, total_amount=total,
            status="Confirmed" if paid_now else "Pending",
        )
        # Composition: the payment is created as part of the booking
        booking.payment = Payment(
            amount=total, method=method,
            status="Paid" if paid_now else "Pending",
            payment_date=date.today() if paid_now else None,
        )
        db.session.add(booking)
        db.session.flush()  # takes the database write lock

        # Re-check after the flush so two guests cannot take the same room
        if not cls.is_room_available(room.room_id, ci, co, exclude_booking_id=booking.booking_id):
            db.session.rollback()
            return None, [clash]

        db.session.commit()
        return booking, []

    @staticmethod
    def cancel_booking(booking, enforce_date=True):
        """Returns an error message, or None when the booking was cancelled."""
        if not booking.is_cancellable:
            return "Only Pending or Confirmed bookings can be cancelled."
        if enforce_date and booking.check_in <= date.today():
            return "Bookings cannot be cancelled on or after the check-in date."

        booking.status = "Cancelled"
        if booking.payment and booking.payment.status == "Paid":
            booking.payment.status = "Refunded"
        db.session.commit()
        return None