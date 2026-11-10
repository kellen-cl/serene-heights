from sqlalchemy import func

from extensions import db
from models import User
from services.auth_service import EMAIL_RE, PHONE_RE


class GuestService:
    """Profile updates and password changes for a logged-in guest."""

    @staticmethod
    def update_profile(user, data):
        """Returns a list of errors (empty list means saved)."""
        full_name = data.get("full_name", "").strip()
        email = data.get("email", "").strip().lower()
        phone = data.get("phone", "").strip()
        address = data.get("address", "").strip()

        errors = []
        if len(full_name) < 3 or len(full_name) > 100:
            errors.append("Full name must be between 3 and 100 characters.")
        if not EMAIL_RE.match(email) or len(email) > 100:
            errors.append("Enter a valid email address.")
        if not PHONE_RE.match(phone):
            errors.append("Enter a valid phone number (7-20 digits).")
        if len(address) > 200:
            errors.append("Address cannot exceed 200 characters.")

        if not errors:
            taken = User.query.filter(
                func.lower(User.email) == email, User.user_id != user.user_id
            ).first()
            if taken:
                errors.append("That email is already used by another account.")
        if errors:
            return errors

        user.email = email
        user.guest.full_name = full_name
        user.guest.phone = phone
        user.guest.address = address or None
        db.session.commit()
        return []

    @staticmethod
    def change_password(user, current, new, confirm):
        errors = []
        if not user.check_password(current or ""):
            errors.append("Your current password is incorrect.")
        if len(new or "") < 6:
            errors.append("New password must be at least 6 characters.")
        if new != confirm:
            errors.append("New passwords do not match.")
        if not errors and user.check_password(new):
            errors.append("New password must be different from the current one.")
        if errors:
            return errors

        user.set_password(new)
        db.session.commit()
        return []