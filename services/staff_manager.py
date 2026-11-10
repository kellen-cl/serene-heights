from datetime import date

from sqlalchemy import func

from extensions import db
from models import Staff, User
from services.auth_service import EMAIL_RE, PHONE_RE, USERNAME_RE


class StaffManager:
    """Create, edit and (de)activate staff accounts. Used by ADMIN only."""
    ROLES = ("STAFF", "ADMIN")

    @classmethod
    def _validate(cls, data, role, user_id=None):
        errors = []
        full_name = data.get("full_name", "").strip()
        email = data.get("email", "").strip().lower()
        phone = data.get("phone", "").strip()
        position = data.get("position", "").strip()

        if len(full_name) < 3 or len(full_name) > 100:
            errors.append("Full name must be between 3 and 100 characters.")
        if not EMAIL_RE.match(email) or len(email) > 100:
            errors.append("Enter a valid email address.")
        if not PHONE_RE.match(phone):
            errors.append("Enter a valid phone number (7-20 digits).")
        if not position or len(position) > 50:
            errors.append("Position is required (max 50 characters).")
        if role not in cls.ROLES:
            errors.append("Role must be STAFF or ADMIN.")

        if not errors and User.query.filter(
            func.lower(User.email) == email, User.user_id != (user_id or 0)
        ).first():
            errors.append("That email is already used by another account.")

        clean = {"full_name": full_name, "email": email, "phone": phone, "position": position}
        return clean, errors

    @classmethod
    def create(cls, data):
        """Returns (staff, errors)."""
        role = data.get("role", "STAFF")
        clean, errors = cls._validate(data, role)
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not USERNAME_RE.match(username):
            errors.append("Username must be 3-50 characters: letters, numbers, _ or . only.")
        elif User.query.filter(func.lower(User.username) == username.lower()).first():
            errors.append("That username is already taken.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if errors:
            return None, errors

        user = User(username=username, email=clean["email"], role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        staff = Staff(
            user_id=user.user_id, full_name=clean["full_name"], phone=clean["phone"],
            position=clean["position"], hire_date=date.today(),
        )
        db.session.add(staff)
        db.session.commit()
        return staff, []

    @classmethod
    def update(cls, staff, data, acting_user):
        """Returns a list of errors (empty list means saved)."""
        role = data.get("role") or staff.user.role  # missing field = unchanged
        if staff.user_id == acting_user.user_id and role != staff.user.role:
            return ["You cannot change your own role."]

        clean, errors = cls._validate(data, role, user_id=staff.user_id)
        if errors:
            return errors

        staff.full_name = clean["full_name"]
        staff.phone = clean["phone"]
        staff.position = clean["position"]
        staff.user.email = clean["email"]
        staff.user.role = role
        db.session.commit()
        return []

    @staticmethod
    def toggle_active(staff, acting_user):
        """Returns an error message, or None when the account was toggled."""
        if staff.user_id == acting_user.user_id:
            return "You cannot deactivate your own account."
        staff.user.is_active = not staff.user.is_active
        db.session.commit()
        return None