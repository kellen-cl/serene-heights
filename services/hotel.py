from datetime import date

from sqlalchemy import func

from extensions import db
from models import Booking, Guest, Payment, Room


class Hotel:
    """Aggregates hotel-wide figures for the admin dashboard."""
    ACTIVE = ("Pending", "Confirmed", "Checked-In")

    @classmethod
    def dashboard_stats(cls):
        today = date.today()

        total_rooms = Room.query.count()
        maintenance = Room.query.filter_by(status="Maintenance").count()

        busy_ids = [
            row[0] for row in db.session.query(Booking.room_id).filter(
                Booking.status.in_(cls.ACTIVE),
                Booking.check_in <= today,
                Booking.check_out > today,
            ).all()
        ]
        free_q = Room.query.filter(Room.status == "Available")
        if busy_ids:
            free_q = free_q.filter(~Room.room_id.in_(busy_ids))

        revenue = db.session.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(Payment.status == "Paid").scalar()

        return {
            "total_rooms": total_rooms,
            "free_rooms": free_q.count(),
            "maintenance_rooms": maintenance,
            "total_guests": Guest.query.count(),
            "total_bookings": Booking.query.count(),
            "arrivals_today": Booking.query.filter(
                Booking.check_in == today, Booking.status.in_(("Pending", "Confirmed"))
            ).count(),
            "checked_in": Booking.query.filter_by(status="Checked-In").count(),
            "revenue": revenue or 0,
            "pending_payments": Payment.query.filter_by(status="Pending").count(),
            "recent_bookings": Booking.query.order_by(Booking.created_at.desc()).limit(8).all(),
        }