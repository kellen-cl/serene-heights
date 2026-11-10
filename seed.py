"""Seed the database.

  python seed.py                  base data (rooms, admin, staff, one guest)
  python seed.py --demo           base data + sample guests/bookings/payments
  python seed.py --reset --demo   WIPE all data, then reseed with demo data
"""
import sys
from datetime import date, datetime, time, timedelta

from app import create_app
from extensions import db
from models import (Booking, DoubleRoom, Guest, Payment, Room, SingleRoom, Staff,
                    Suite, User)

app = create_app()


def _make_user(username, email, role, password):
    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def seed_base():
    admin_u = _make_user("admin", "admin@serenehights.com", "ADMIN", "Admin@123")
    staff_u = _make_user("reception", "reception@serenehights.com", "STAFF", "Staff@123")
    guest_u = _make_user("jane", "jane@example.com", "GUEST", "Guest@123")

    db.session.add_all([
        Staff(user_id=admin_u.user_id, full_name="Hotel Administrator", phone="0700000001",
              position="Administrator", hire_date=date.today()),
        Staff(user_id=staff_u.user_id, full_name="Sam Receptionist", phone="0700000002",
              position="Reception", hire_date=date.today()),
        Guest(user_id=guest_u.user_id, full_name="Jane Wanjiru", phone="0711111111",
              id_number="12345678", address="Nairobi"),
    ])

    single_am = "WiFi, TV, Air Conditioning, Work Desk"
    double_am = "WiFi, TV, Air Conditioning, Breakfast, Mini Fridge"
    suite_am = "WiFi, Smart TV, Air Conditioning, Breakfast, Mini Bar, Balcony, Lounge Area"

    db.session.add_all([
        SingleRoom(room_number="101", price_per_night=50, capacity=1, amenities=single_am,
                   description="A calm, compact room ideal for solo travellers."),
        SingleRoom(room_number="102", price_per_night=50, capacity=1, amenities=single_am,
                   description="A calm, compact room ideal for solo travellers."),
        SingleRoom(room_number="103", price_per_night=55, capacity=1, amenities=single_am,
                   description="A bright single room overlooking the garden."),
        DoubleRoom(room_number="201", price_per_night=80, capacity=2, amenities=double_am,
                   description="A spacious double room with a king-size bed."),
        DoubleRoom(room_number="202", price_per_night=80, capacity=2, amenities=double_am,
                   description="A spacious double room with a king-size bed."),
        DoubleRoom(room_number="203", price_per_night=85, capacity=2, amenities=double_am,
                   description="A double room with a private sitting nook."),
        DoubleRoom(room_number="204", price_per_night=80, capacity=2, amenities=double_am,
                   status="Maintenance", description="Currently under refurbishment."),
        Suite(room_number="301", price_per_night=150, capacity=4, amenities=suite_am,
              description="Our signature suite with a separate lounge and balcony."),
        Suite(room_number="302", price_per_night=170, capacity=4, amenities=suite_am,
              description="A top-floor suite with panoramic views."),
    ])
    db.session.commit()
    print("Base data seeded.")


# (username, full name, email, phone, id number, address)
DEMO_GUESTS = [
    ("amina", "Amina Hassan", "amina@example.com", "0722000001", "23456789", "Mombasa"),
    ("peter", "Peter Otieno", "peter@example.com", "0733000002", "34567890", "Kisumu"),
    ("grace", "Grace Njeri", "grace@example.com", "0744000003", "45678901", "Nakuru"),
    ("daniel", "Daniel Kimani", "daniel@example.com", "0755000004", "56789012", "Nairobi"),
]

# (guest, room, check-in offset, check-out offset in days from today, status, method, payment status)
DEMO_BOOKINGS = [
    ("jane",   "201", -25, -22, "Completed",  "Card",         "Paid"),
    ("amina",  "301", -18, -13, "Completed",  "Mobile Money", "Paid"),
    ("peter",  "101", -12, -10, "Completed",  "Cash",         "Paid"),
    ("grace",  "202",  -8,  -5, "Completed",  "Card",         "Paid"),
    ("jane",   "102",  -1,   2, "Checked-In", "Mobile Money", "Paid"),
    ("amina",  "203",  -1,   2, "Checked-In", "Card",         "Paid"),
    ("grace",  "301",   5,   8, "Confirmed",  "Card",         "Paid"),
    ("daniel", "201",   6,   9, "Confirmed",  "Mobile Money", "Paid"),
    ("peter",  "103",  10,  12, "Pending",    "Cash",         "Pending"),
    ("daniel", "202",   3,   4, "Cancelled",  "Card",         "Refunded"),
]


def seed_demo():
    if Booking.query.first():
        print("Demo data skipped: bookings already exist (use --reset to start fresh).")
        return
    if not Room.query.filter_by(room_number="201").first():
        print("Demo data skipped: base rooms are missing.")
        return

    for username, name, email, phone, id_number, address in DEMO_GUESTS:
        if User.query.filter_by(username=username).first():
            continue
        user = _make_user(username, email, "GUEST", "Guest@123")
        db.session.add(Guest(user_id=user.user_id, full_name=name, phone=phone,
                             id_number=id_number, address=address))
    db.session.flush()

    today = date.today()
    reception = User.query.filter_by(username="reception").first().staff

    for username, number, a, b, status, method, pay_status in DEMO_BOOKINGS:
        user = User.query.filter_by(username=username).first()
        room = Room.query.filter_by(room_number=number).first()
        check_in, check_out = today + timedelta(days=a), today + timedelta(days=b)
        total = room.calculate_price((check_out - check_in).days)
        paid_like = pay_status in ("Paid", "Refunded")
        anchor = min(check_in, today)

        booking = Booking(
            guest_id=user.guest.guest_id, room_id=room.room_id,
            handled_by=None if status == "Pending" else reception.staff_id,
            check_in=check_in, check_out=check_out, num_guests=min(2, room.capacity),
            total_amount=total, status=status,
            created_at=datetime.combine(anchor - timedelta(days=3), time(10, 0)),
        )
        booking.payment = Payment(
            amount=total, method=method, status=pay_status,
            payment_date=anchor if paid_like else None,
            processed_by=reception.staff_id if paid_like else None,
        )
        db.session.add(booking)

    db.session.commit()
    print(f"Demo data seeded: {len(DEMO_GUESTS)} guests, {len(DEMO_BOOKINGS)} bookings.")


if __name__ == "__main__":
    flags = sys.argv[1:]
    with app.app_context():
        if "--reset" in flags:
            db.drop_all()
            db.create_all()
            print("All tables wiped and recreated.")

        if User.query.first():
            print("Base data already present.")
        else:
            seed_base()

        if "--demo" in flags:
            seed_demo()

        print("\nLogins:")
        print("  Admin:      admin / Admin@123      (/admin/login)")
        print("  Staff:      reception / Staff@123  (/admin/login)")
        print("  Guest:      jane / Guest@123       (/login)")
        if "--demo" in flags:
            print("  More guests: amina, peter, grace, daniel / Guest@123")