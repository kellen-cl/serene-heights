from abc import ABC, abstractmethod
from datetime import timedelta

from models import Booking, Payment, Room


def _d(value):
    return value.strftime("%d %b %Y")


class Report(ABC):
    """Abstract base class. Each subclass implements generate() differently (polymorphism).

    generate() returns a dict:
      columns: list of (label, kind)   kind is "text", "num", "money" or "pct"
      rows:    list of lists matching the columns
      summary: list of (label, value, kind)
    """
    key = ""
    label = ""

    @abstractmethod
    def generate(self, start, end):
        ...

    def _result(self, columns, rows, summary):
        return {"title": self.label, "columns": columns, "rows": rows, "summary": summary}


class BookingReport(Report):
    key = "bookings"
    label = "Booking Report"

    def generate(self, start, end):
        bookings = (Booking.query
                    .filter(Booking.check_in >= start, Booking.check_in <= end)
                    .order_by(Booking.check_in, Booking.booking_id).all())
        columns = [("Booking", "text"), ("Guest", "text"), ("Room", "text"),
                   ("Check-in", "text"), ("Check-out", "text"), ("Nights", "num"),
                   ("Total", "money"), ("Status", "text")]
        rows = [[b.reference, b.guest.full_name, b.room.room_number, _d(b.check_in),
                 _d(b.check_out), b.nights, float(b.total_amount), b.status] for b in bookings]
        cancelled = sum(1 for b in bookings if b.status == "Cancelled")
        value = sum(float(b.total_amount) for b in bookings if b.status != "Cancelled")
        summary = [("Bookings (by check-in date)", len(bookings), "num"),
                   ("Cancelled", cancelled, "num"),
                   ("Booked value (excl. cancelled)", value, "money")]
        return self._result(columns, rows, summary)


class RevenueReport(Report):
    key = "revenue"
    label = "Revenue Report"
    METHODS = ("Cash", "Card", "Mobile Money")

    def generate(self, start, end):
        paid = (Payment.query
                .filter(Payment.status == "Paid", Payment.payment_date >= start,
                        Payment.payment_date <= end)
                .order_by(Payment.payment_date, Payment.payment_id).all())
        refunded = (Payment.query
                    .filter(Payment.status == "Refunded", Payment.payment_date >= start,
                            Payment.payment_date <= end).all())
        columns = [("Payment", "num"), ("Booking", "text"), ("Guest", "text"),
                   ("Method", "text"), ("Date", "text"), ("Amount", "money")]
        rows = [[p.payment_id, p.booking.reference, p.booking.guest.full_name, p.method,
                 _d(p.payment_date), float(p.amount)] for p in paid]
        summary = [("Total revenue (paid)", sum(float(p.amount) for p in paid), "money"),
                   ("Payments received", len(paid), "num")]
        for method in self.METHODS:
            summary.append((f"  {method}", sum(float(p.amount) for p in paid if p.method == method), "money"))
        summary.append(("Refunded (not counted above)", sum(float(p.amount) for p in refunded), "money"))
        return self._result(columns, rows, summary)


class OccupancyReport(Report):
    key = "occupancy"
    label = "Occupancy Report"
    COUNTED = ("Confirmed", "Checked-In", "Completed")

    def generate(self, start, end):
        end_excl = end + timedelta(days=1)  # a night is occupied when check_in <= day < check_out
        days = (end_excl - start).days
        rooms = Room.query.order_by(Room.room_number).all()
        bookings = Booking.query.filter(
            Booking.status.in_(self.COUNTED),
            Booking.check_in < end_excl, Booking.check_out > start,
        ).all()

        nights_by_room = {}
        for b in bookings:
            nights = (min(b.check_out, end_excl) - max(b.check_in, start)).days
            nights_by_room[b.room_id] = nights_by_room.get(b.room_id, 0) + max(nights, 0)

        columns = [("Room", "text"), ("Type", "text"), ("Nights occupied", "num"),
                   ("Days in period", "num"), ("Occupancy", "pct")]
        rows, total_nights = [], 0
        for r in rooms:
            n = nights_by_room.get(r.room_id, 0)
            total_nights += n
            rows.append([r.room_number, r.room_type, n, days, n / days * 100])

        capacity = len(rooms) * days
        overall = (total_nights / capacity * 100) if capacity else 0
        summary = [("Overall occupancy", overall, "pct"),
                   ("Room-nights occupied", total_nights, "num"),
                   ("Room-nights available", capacity, "num")]
        return self._result(columns, rows, summary)


REPORTS = {cls.key: cls for cls in (BookingReport, RevenueReport, OccupancyReport)}