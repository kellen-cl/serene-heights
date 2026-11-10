from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from extensions import db
from models import Booking, Room
from services.auth_service import AuthService, guest_required
from services.booking_manager import BookingManager
from services.guest_service import GuestService

bp = Blueprint("guest", __name__)
ROOM_TYPES = ("Single", "Double", "Suite")


def _card(room, stay=None, nights=None, total=None):
    """Data for one room card (used on home, search results and browse list)."""
    return {
        "room": room,
        "nights": nights,
        "total": total,
        "url": url_for("guest.room_detail", room_id=room.room_id, **(stay or {})),
    }


def _own_booking_or_404(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.guest_id != AuthService.current_user().guest.guest_id:
        abort(404)
    return booking


# ---------------- Public pages ----------------
@bp.route("/")
def index():
    featured = []
    for room_type in ROOM_TYPES:
        room = (Room.query.filter_by(room_type=room_type, status="Available")
                .order_by(Room.price_per_night).first())
        if room:
            featured.append(_card(room))
    return render_template("guest/index.html", featured=featured)


@bp.route("/rooms")
def rooms():
    """F4 (search form) + F5 (available rooms). With no dates it lists all rooms."""
    args = request.args
    form = {
        "check_in": args.get("check_in", "").strip(),
        "check_out": args.get("check_out", "").strip(),
        "guests": args.get("guests", "2").strip(),
        "room_type": args.get("room_type", "").strip(),
    }
    room_type = form["room_type"] if form["room_type"] in ROOM_TYPES else None

    results, summary = None, None
    if form["check_in"] or form["check_out"]:
        ci, co, n, errors = BookingManager.validate_stay(
            form["check_in"], form["check_out"], form["guests"]
        )
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            nights = (co - ci).days
            stay = {"check_in": ci.isoformat(), "check_out": co.isoformat(), "guests": n}
            found = BookingManager.search_available(ci, co, n, room_type)
            results = [_card(r, stay, nights, r.calculate_price(nights)) for r in found]
            summary = {"check_in": ci, "check_out": co, "nights": nights, "guests": n}

    browse = None
    if results is None:
        q = Room.query.filter_by(status="Available")
        if room_type:
            q = q.filter_by(room_type=room_type)
        browse = [_card(r) for r in q.order_by(Room.price_per_night, Room.room_number)]

    today = date.today()
    return render_template(
        "guest/rooms.html", form=form, results=results, summary=summary, browse=browse,
        room_types=ROOM_TYPES, today=today.isoformat(),
        tomorrow=(today + timedelta(days=1)).isoformat(),
    )


@bp.route("/rooms/<int:room_id>")
def room_detail(room_id):
    """F6: room details, with a live availability check when dates are given."""
    room = db.get_or_404(Room, room_id)
    args = request.args
    form = {
        "check_in": args.get("check_in", "").strip(),
        "check_out": args.get("check_out", "").strip(),
        "guests": args.get("guests", "1").strip(),
    }

    stay, book_url = None, None
    if form["check_in"] or form["check_out"]:
        ci, co, n, errors = BookingManager.validate_stay(
            form["check_in"], form["check_out"], form["guests"]
        )
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            nights = (co - ci).days
            if not room.is_bookable:
                state = "maintenance"
            elif n > room.capacity:
                state = "capacity"
            elif not BookingManager.is_room_available(room.room_id, ci, co):
                state = "booked"
            else:
                state = "ok"
                book_url = url_for("guest.reserve", room_id=room.room_id,
                                   check_in=ci.isoformat(), check_out=co.isoformat(), guests=n)
            stay = {"check_in": ci, "check_out": co, "nights": nights, "guests": n,
                    "total": room.calculate_price(nights), "state": state}

    today = date.today()
    return render_template(
        "guest/room_detail.html", room=room, form=form, stay=stay, book_url=book_url,
        today=today.isoformat(), tomorrow=(today + timedelta(days=1)).isoformat(),
    )


# ---------------- Authentication ----------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    user = AuthService.current_user()
    if user and user.role == "GUEST":
        return redirect(url_for("guest.home"))

    if request.method == "POST":
        user, error = AuthService.authenticate(
            request.form.get("username"), request.form.get("password"), ("GUEST",)
        )
        if error:
            flash(error, "danger")
        else:
            AuthService.login(user)
            flash(f"Welcome back, {user.guest.full_name.split()[0]}!", "success")
            return redirect(url_for("guest.home"))
    return render_template("guest/login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        guest, errors = AuthService.register_guest(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("guest/register.html", form=request.form)
        flash("Account created. Please log in.", "success")
        return redirect(url_for("guest.login"))
    return render_template("guest/register.html", form={})


@bp.route("/logout", methods=["POST"])
def logout():
    AuthService.logout()
    flash("You have been logged out.", "info")
    return redirect(url_for("guest.index"))


# ---------------- Guest area ----------------
@bp.route("/home")
@guest_required
def home():
    guest = AuthService.current_user().guest
    next_booking = (
        Booking.query.filter(
            Booking.guest_id == guest.guest_id,
            Booking.status.in_(("Pending", "Confirmed")),
            Booking.check_out >= date.today(),
        )
        .order_by(Booking.check_in)
        .first()
    )
    return render_template("guest/home.html", guest=guest, next_booking=next_booking)


@bp.route("/reserve/<int:room_id>", methods=["GET", "POST"])
@guest_required
def reserve(room_id):
    """F7: review the booking, choose a payment method, confirm."""
    room = db.get_or_404(Room, room_id)
    user = AuthService.current_user()
    src = request.form if request.method == "POST" else request.args
    stay_args = {
        "check_in": src.get("check_in", "").strip(),
        "check_out": src.get("check_out", "").strip(),
        "guests": src.get("guests", "1").strip(),
    }
    method = src.get("payment_method", "")

    if request.method == "POST":
        booking, errors = BookingManager.create_booking(
            user.guest, room, stay_args["check_in"], stay_args["check_out"],
            stay_args["guests"], method,
        )
        if not errors:
            flash("Your booking has been created.", "success")
            return redirect(url_for("guest.booking_confirmation", booking_id=booking.booking_id))
        for e in errors:
            flash(e, "danger")

    back = redirect(url_for("guest.room_detail", room_id=room_id, **stay_args))
    ci, co, n, errors = BookingManager.validate_stay(
        stay_args["check_in"], stay_args["check_out"], stay_args["guests"]
    )
    if errors:
        if request.method == "GET":
            for e in errors:
                flash(e, "danger")
        return back

    available = (room.is_bookable and n <= room.capacity
                 and BookingManager.is_room_available(room.room_id, ci, co))
    if not available:
        if request.method == "GET":
            flash("Sorry, this room is not available for those dates.", "danger")
        return back

    nights = (co - ci).days
    total = room.calculate_price(nights)
    subtotal = round(room.price_per_night * nights, 2)
    return render_template(
        "guest/reserve.html", room=room, guest=user.guest, user=user,
        check_in=ci, check_out=co, nights=nights, num_guests=n,
        subtotal=subtotal, discount=round(subtotal - total, 2), total=total,
        methods=BookingManager.PAYMENT_METHODS, method=method,
    )


@bp.route("/bookings/<int:booking_id>")
@guest_required
def booking_confirmation(booking_id):
    """F8: confirmation / booking details."""
    booking = _own_booking_or_404(booking_id)
    return render_template("guest/confirmation.html", booking=booking, today=date.today())


@bp.route("/my-bookings")
@guest_required
def my_bookings():
    """F9: the guest's booking history."""
    guest = AuthService.current_user().guest
    bookings = (Booking.query.filter_by(guest_id=guest.guest_id)
                .order_by(Booking.created_at.desc()).all())
    return render_template("guest/my_bookings.html", bookings=bookings, today=date.today())


@bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@guest_required
def cancel_booking(booking_id):
    booking = _own_booking_or_404(booking_id)
    error = BookingManager.cancel_booking(booking)
    if error:
        flash(error, "danger")
    else:
        flash(f"Booking {booking.reference} has been cancelled.", "success")
    return redirect(url_for("guest.my_bookings"))


@bp.route("/profile", methods=["GET", "POST"])
@guest_required
def profile():
    """F10: view and update personal information."""
    user = AuthService.current_user()
    if request.method == "POST":
        errors = GuestService.update_profile(user, request.form)
        if not errors:
            flash("Profile updated.", "success")
            return redirect(url_for("guest.profile"))
        for e in errors:
            flash(e, "danger")
        return render_template("guest/profile.html", user=user, form=request.form)
    return render_template("guest/profile.html", user=user, form={})


@bp.route("/profile/password", methods=["POST"])
@guest_required
def change_password():
    user = AuthService.current_user()
    errors = GuestService.change_password(
        user, request.form.get("current_password"),
        request.form.get("new_password"), request.form.get("confirm_password"),
    )
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        flash("Password changed successfully.", "success")
    return redirect(url_for("guest.profile"))