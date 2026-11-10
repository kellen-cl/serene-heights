import re
from functools import wraps

from flask import flash, g, redirect, session, url_for
from sqlalchemy import func

from extensions import db
from models import Guest, User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,50}$")
PHONE_RE = re.compile(r"^\+?[0-9\s-]{7,20}$")


class AuthService:
    """Handles registration, login, sessions and access checks."""

    # ---------- Registration ----------
    @staticmethod
    def validate_registration(data):
        errors = []
        full_name = data.get("full_name", "").strip()
        email = data.get("email", "").strip().lower()
        phone = data.get("phone", "").strip()
        id_number = data.get("id_number", "").strip()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        confirm = data.get("confirm_password", "")

        if len(full_name) < 3 or len(full_name) > 100:
            errors.append("Full name must be between 3 and 100 characters.")
        if not EMAIL_RE.match(email) or len(email) > 100:
            errors.append("Enter a valid email address.")
        if not PHONE_RE.match(phone):
            errors.append("Enter a valid phone number (7-20 digits).")
        if len(id_number) < 5 or len(id_number) > 30:
            errors.append("ID/passport number must be between 5 and 30 characters.")
        if not USERNAME_RE.match(username):
            errors.append("Username must be 3-50 characters: letters, numbers, _ or . only.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if not errors:
            if User.query.filter(func.lower(User.username) == username.lower()).first():
                errors.append("That username is already taken.")
            if User.query.filter(func.lower(User.email) == email).first():
                errors.append("That email is already registered.")
            if Guest.query.filter_by(id_number=id_number).first():
                errors.append("That ID/passport number is already registered.")
        return errors

    @staticmethod
    def register_guest(data):
        """Returns (guest, errors). Creates the users row and the guests row."""
        errors = AuthService.validate_registration(data)
        if errors:
            return None, errors

        user = User(
            username=data["username"].strip(),
            email=data["email"].strip().lower(),
            role="GUEST",
        )
        user.set_password(data["password"])
        db.session.add(user)
        db.session.flush()

        guest = Guest(
            user_id=user.user_id,
            full_name=data["full_name"].strip(),
            phone=data["phone"].strip(),
            id_number=data["id_number"].strip(),
        )
        db.session.add(guest)
        db.session.commit()
        return guest, []

    # ---------- Login / session ----------
    @staticmethod
    def authenticate(identifier, password, allowed_roles):
        """Returns (user, error_message)."""
        identifier = (identifier or "").strip()
        user = User.query.filter(
            (func.lower(User.username) == identifier.lower())
            | (func.lower(User.email) == identifier.lower())
        ).first()

        if not user or not user.check_password(password or ""):
            return None, "Invalid username or password."
        if not user.is_active:
            return None, "This account has been deactivated."
        if user.role not in allowed_roles:
            if user.role == "GUEST":
                return None, "This is a guest account. Please use the Guest Login."
            return None, "This is a staff account. Please use the Admin Login."
        return user, None

    @staticmethod
    def login(user):
        session.clear()
        session["user_id"] = user.user_id
        session["role"] = user.role

    @staticmethod
    def logout():
        session.clear()

    @staticmethod
    def current_user():
        if "current_user" not in g:
            user = None
            user_id = session.get("user_id")
            if user_id:
                user = db.session.get(User, user_id)
                if user and not user.is_active:
                    user = None
            g.current_user = user
        return g.current_user


# ---------- Access-control decorators ----------
def guest_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = AuthService.current_user()
        if not user or user.role != "GUEST":
            flash("Please log in to continue.", "warning")
            return redirect(url_for("guest.login"))
        return view(*args, **kwargs)
    return wrapped


def staff_required(view):
    """STAFF and ADMIN may enter the admin panel."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = AuthService.current_user()
        if not user or not user.is_staff_member:
            flash("Please log in with a staff account.", "warning")
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """ADMIN only (e.g. staff management)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = AuthService.current_user()
        if not user or not user.is_staff_member:
            flash("Please log in with a staff account.", "warning")
            return redirect(url_for("admin.login"))
        if not user.is_admin:
            flash("Only administrators can access that page.", "danger")
            return redirect(url_for("admin.dashboard"))
        return view(*args, **kwargs)
    return wrapped