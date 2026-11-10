# Serene Heights – Hotel Management System

CMT 210 Object Oriented Programming I | Group CwK
Flask + SQLAlchemy + SQLite + Bootstrap 5. Database name: `CwK_Hotel_Management_DB`.

## Run

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    python seed.py --demo        # rooms, accounts and sample bookings
    python app.py                # http://127.0.0.1:5000

`python seed.py --reset --demo` wipes the database and reseeds it.

## Demo accounts


## Demo accounts

Demo accounts can be generated locally using:

`python seed.py --demo`

For security reasons, demo usernames and passwords are not published in this repository. Change all seeded account passwords before deploying the application publicly.


## Screens (Deliverable 2) and where they live

| Screen | URL | Screen | URL |
|---|---|---|---|
| F1 Guest Login | /login | A1 Admin Login | /admin/login |
| F2 Registration | /register | A2 Dashboard | /admin/ |
| F3 Home | /home | A3 Room Management | /admin/rooms |
| F4/F5 Search + Available Rooms | /rooms | A4 Guest Management | /admin/guests |
| F6 Room Details | /rooms/<id> | A5 Booking Management | /admin/bookings |
| F7 Reservation | /reserve/<id> | A6 Payment Management | /admin/payments |
| F8 Confirmation | /bookings/<id> | A7 Staff Management (ADMIN) | /admin/staff |
| F9 My Bookings | /my-bookings | A8 Reports | /admin/reports |
| F10 Profile | /profile | A9 Logout | /admin/logout |

## OOP in the code

| Concept | Where |
|---|---|
| Classes / objects | `models/`: User, Guest, Staff, Room, Booking, Payment |
| Inheritance | Guest and Staff extend Person; SingleRoom, DoubleRoom, Suite extend Room; BookingReport, RevenueReport, OccupancyReport extend Report |
| Polymorphism | `Room.calculate_price()` (Suite overrides: 10% off 5+ nights); `get_permissions()` (Guest, Staff); `Report.generate()` |
| Abstraction | Person and Report are abstract base classes |
| Encapsulation | Passwords only set or checked via `set_password()` / `check_password()`; validation in `models` and `services` |
| Association | Booking references one Guest and one Room; Staff handles Bookings |
| Composition | Payment is created with, and deleted with, its Booking |
| Aggregation | `services/hotel.py` aggregates rooms, guests, bookings and payments |

## Rules enforced

- Passwords are hashed (Werkzeug); admin routes require STAFF/ADMIN; Staff Management is ADMIN only.
- Double-booking prevented: overlap when `new_in < existing_out AND new_out > existing_in`, re-checked inside the write transaction.
- Maintenance rooms are never offered; dates, guests, prices and statuses are validated; database CHECK and FOREIGN KEY constraints are on.
- Payments are simulated only (Card and Mobile Money are marked Paid instantly; Cash stays Pending).

## Differences from Deliverable 2 (deliberate)

- Guest and Staff extend an abstract `Person` class, not `User`, because each has its own table and primary key linked to `users` by `user_id`.
- An Admin is a Staff record whose user role is `ADMIN` (no separate class or table).
- Room images are chosen by room type, because the `rooms` table has no image column.