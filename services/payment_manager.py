from datetime import date

from extensions import db


class PaymentManager:
    """Staff actions on payment records. Return an error message, or None on success."""

    @staticmethod
    def mark_paid(payment, staff):
        if payment.status != "Pending":
            return "Only Pending payments can be marked as paid."
        booking = payment.booking
        if booking.status == "Cancelled":
            return "This booking is cancelled, so its payment cannot be collected."

        payment.status = "Paid"
        payment.payment_date = date.today()
        payment.processed_by = staff.staff_id
        if booking.status == "Pending":  # cash received, so the booking is confirmed
            booking.status = "Confirmed"
            booking.handled_by = staff.staff_id
        db.session.commit()
        return None

    @staticmethod
    def refund(payment, staff):
        if payment.status != "Paid":
            return "Only Paid payments can be refunded."
        booking = payment.booking
        if booking.status == "Checked-In":
            return "The guest is checked in. Check the guest out before refunding."

        if booking.status in ("Pending", "Confirmed"):  # a refunded stay no longer stands
            booking.status = "Cancelled"
            booking.handled_by = staff.staff_id
        payment.status = "Refunded"
        payment.processed_by = staff.staff_id
        db.session.commit()
        return None