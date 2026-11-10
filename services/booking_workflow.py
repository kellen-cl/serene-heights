from datetime import date

from extensions import db
from services.booking_manager import BookingManager


class BookingWorkflow:
    """Staff actions that move a booking through its lifecycle.

    Every method returns an error message, or None when the action succeeded.
    """
    # Set to False during demos to allow check-in before the booked date
    ENFORCE_CHECKIN_DATE = True

    @staticmethod
    def confirm(booking, staff):
        if booking.status != "Pending":
            return "Only Pending bookings can be confirmed."
        booking.status = "Confirmed"
        booking.handled_by = staff.staff_id
        db.session.commit()
        return None

    @classmethod
    def check_in(cls, booking, staff):
        if booking.status != "Confirmed":
            return "Only Confirmed bookings can be checked in. Confirm the booking first."
        today = date.today()
        if cls.ENFORCE_CHECKIN_DATE and booking.check_in > today:
            return f"Check-in opens on {booking.check_in.strftime('%d %b %Y')}."
        if booking.check_out <= today:
            return "The dates of this stay have already passed."
        if not booking.room.is_bookable:
            return f"Room {booking.room.room_number} is under maintenance."
        booking.status = "Checked-In"
        booking.handled_by = staff.staff_id
        db.session.commit()
        return None

    @staticmethod
    def check_out(booking, staff):
        if booking.status != "Checked-In":
            return "Only Checked-In bookings can be checked out."
        if booking.payment and booking.payment.status != "Paid":
            return "Payment is still pending. Mark it as paid in Payment Management first."
        booking.status = "Completed"
        booking.handled_by = staff.staff_id
        db.session.commit()
        return None

    @staticmethod
    def cancel(booking, staff):
        error = BookingManager.cancel_booking(booking, enforce_date=False)
        if error:
            return error
        booking.handled_by = staff.staff_id
        db.session.commit()
        return None