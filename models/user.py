
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import validates

from extensions import db


class User(db.Model):
    """Login account for guests, staff and administrators."""

    __tablename__ = "users"

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('GUEST','STAFF','ADMIN')",
            name="ck_users_role"
        ),
    )

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    guest = db.relationship("Guest", back_populates="user", uselist=False)
    staff = db.relationship("Staff", back_populates="user", uselist=False)

    @validates("role")
    def _validate_role(self, key, value):
        value = value.upper()

        if value not in ("GUEST", "STAFF", "ADMIN"):
            raise ValueError("Role must be GUEST, STAFF or ADMIN")

        return value

    # Encapsulation: passwords are managed through these methods.
    def set_password(self, raw_password):
        if len(raw_password) < 6:
            raise ValueError("Password must be at least 6 characters")

        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)

    @property
    def is_admin(self):
        return self.role == "ADMIN"

    @property
    def is_staff_member(self):
        return self.role in ("STAFF", "ADMIN")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Person(db.Model):
    """Abstract parent class for people linked to user accounts."""

    __abstract__ = True

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        unique=True,
        nullable=False
    )

    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    def get_permissions(self):
        raise NotImplementedError(
            "Subclasses must define permissions"
        )


class Guest(Person):
    """Hotel customer."""

    __tablename__ = "guests"

    guest_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_number = db.Column(db.String(30), unique=True, nullable=False)
    address = db.Column(db.String(200), nullable=True)

    user = db.relationship("User", back_populates="guest")
    bookings = db.relationship("Booking", back_populates="guest")

    def get_permissions(self):
        return [
            "search_rooms",
            "make_booking",
            "view_own_bookings",
            "edit_profile"
        ]

    def __repr__(self):
        return f"<Guest {self.full_name}>"


class Staff(Person):
    """Hotel employee or administrator."""

    __tablename__ = "staff"

    staff_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position = db.Column(db.String(50), nullable=False)
    hire_date = db.Column(db.Date, nullable=False)

    user = db.relationship("User", back_populates="staff")

    bookings_handled = db.relationship(
        "Booking", back_populates="handler"
    )

    payments_processed = db.relationship(
        "Payment", back_populates="processor"
    )

    @property
    def is_admin(self):
        return self.user.role == "ADMIN"

    def get_permissions(self):
        permissions = [
            "manage_rooms",
            "manage_bookings",
            "manage_payments",
            "view_guests",
            "view_reports"
        ]

        if self.is_admin:
            permissions.append("manage_staff")

        return permissions

    def __repr__(self):
        return f"<Staff {self.full_name}>"
