import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from extensions import db
from models import Booking, Guest, Payment, Room, Staff, User
from models.booking import BOOKING_STATUSES
from services.auth_service import AuthService, admin_required, staff_required
from services.booking_manager import BookingManager
from services.booking_workflow import BookingWorkflow
from services.guest_service import GuestService
from services.hotel import Hotel
from services.payment_manager import PaymentManager
from services.report import REPORTS
from services.room_manager import RoomManager
from services.staff_manager import StaffManager

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _flash_result(error, success_message):
    flash(error or success_message, "danger" if error else "success")


# ---------------- A1 / A9: login and logout ----------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    user = AuthService.current_user()
    if user and user.is_staff_member:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        user, error = AuthService.authenticate(
            request.form.get("username"), request.form.get("password"), ("STAFF", "ADMIN")
        )
        if error:
            flash(error, "danger")
        else:
            AuthService.login(user)
            return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html")


@bp.route("/logout", methods=["GET", "POST"])
@staff_required
def logout():
    """GET shows the confirmation, POST ends the session."""
    if request.method == "POST":
        AuthService.logout()
        flash("You have been logged out.", "info")
        return redirect(url_for("admin.login"))
    return render_template("admin/logout_confirm.html")


# ---------------- A2: dashboard ----------------
@bp.route("/")
@staff_required
def dashboard():
    return render_template("admin/dashboard.html", stats=Hotel.dashboard_stats())


# ---------------- A3: room management ----------------
@bp.route("/rooms")
@staff_required
def rooms():
    type_f = request.args.get("type", "")
    status_f = request.args.get("status", "")
    q = Room.query
    if type_f in RoomManager.TYPES:
        q = q.filter_by(room_type=type_f)
    if status_f in RoomManager.STATUSES:
        q = q.filter_by(status=status_f)
    return render_template(
        "admin/rooms.html", rooms=q.order_by(Room.room_number).all(),
        types=RoomManager.TYPES, statuses=RoomManager.STATUSES,
        type_f=type_f, status_f=status_f,
    )


@bp.route("/rooms/add", methods=["POST"])
@staff_required
def add_room():
    room, errors = RoomManager.create(request.form)
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        flash(f"Room {room.room_number} added.", "success")
    return redirect(url_for("admin.rooms"))


@bp.route("/rooms/<int:room_id>/edit", methods=["POST"])
@staff_required
def edit_room(room_id):
    room = db.get_or_404(Room, room_id)
    errors = RoomManager.update(room, request.form)
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        flash(f"Room {room.room_number} updated.", "success")
    return redirect(url_for("admin.rooms"))


@bp.route("/rooms/<int:room_id>/delete", methods=["POST"])
@staff_required
def delete_room(room_id):
    room = db.get_or_404(Room, room_id)
    number = room.room_number
    error = RoomManager.delete(room)
    _flash_result(error, f"Room {number} deleted.")
    return redirect(url_for("admin.rooms"))


# ---------------- A4: guest management ----------------
@bp.route("/guests")
@staff_required
def guests():
    term = request.args.get("q", "").strip()
    q = Guest.query.join(User, Guest.user_id == User.user_id)
    if term:
        like = f"%{term}%"
        q = q.filter(or_(
            Guest.full_name.ilike(like), Guest.phone.ilike(like),
            Guest.id_number.ilike(like), User.email.ilike(like), User.username.ilike(like),
        ))
    return render_template("admin/guests.html", guests=q.order_by(Guest.guest_id).all(), term=term)


@bp.route("/guests/<int:guest_id>")
@staff_required
def guest_detail(guest_id):
    guest = db.get_or_404(Guest, guest_id)
    bookings = sorted(guest.bookings, key=lambda b: b.created_at, reverse=True)
    return render_template("admin/guest_detail.html", guest=guest, bookings=bookings)


@bp.route("/guests/<int:guest_id>/edit", methods=["POST"])
@staff_required
def edit_guest(guest_id):
    guest = db.get_or_404(Guest, guest_id)
    errors = GuestService.update_profile(guest.user, request.form)
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        flash(f"{guest.full_name} updated.", "success")
    return redirect(url_for("admin.guests"))


@bp.route("/guests/<int:guest_id>/toggle", methods=["POST"])
@staff_required
def toggle_guest(guest_id):
    guest = db.get_or_404(Guest, guest_id)
    user = guest.user
    user.is_active = not user.is_active
    db.session.commit()
    flash(f"{guest.full_name} has been {'activated' if user.is_active else 'deactivated'}.",
          "success" if user.is_active else "warning")
    return redirect(url_for("admin.guests"))


# ---------------- A5: booking management ----------------
@bp.route("/bookings")
@staff_required
def bookings():
    status_f = request.args.get("status", "")
    term = request.args.get("q", "").strip()

    q = (Booking.query
         .join(Guest, Booking.guest_id == Guest.guest_id)
         .join(Room, Booking.room_id == Room.room_id))
    if status_f in BOOKING_STATUSES:
        q = q.filter(Booking.status == status_f)
    if term:
        like = f"%{term}%"
        conditions = [Guest.full_name.ilike(like), Room.room_number.ilike(like)]
        digits = term.upper().replace("BK-", "").strip()
        if digits.isdigit():
            conditions.append(Booking.booking_id == int(digits))
        q = q.filter(or_(*conditions))

    return render_template(
        "admin/bookings.html", bookings=q.order_by(Booking.created_at.desc()).limit(200).all(),
        statuses=BOOKING_STATUSES, status_f=status_f, term=term, today=date.today(),
        enforce_checkin=BookingWorkflow.ENFORCE_CHECKIN_DATE,
    )


@bp.route("/bookings/<int:booking_id>/<action>", methods=["POST"])
@staff_required
def booking_action(booking_id, action):
    actions = {
        "confirm": (BookingWorkflow.confirm, "confirmed"),
        "check-in": (BookingWorkflow.check_in, "checked in"),
        "check-out": (BookingWorkflow.check_out, "checked out"),
        "cancel": (BookingWorkflow.cancel, "cancelled"),
    }
    if action not in actions:
        abort(404)
    booking = db.get_or_404(Booking, booking_id)
    handler, done = actions[action]
    staff = AuthService.current_user().staff
    _flash_result(handler(booking, staff), f"Booking {booking.reference} {done}.")
    return redirect(url_for("admin.bookings"))


# ---------------- A6: payment management ----------------
@bp.route("/payments")
@staff_required
def payments():
    status_f = request.args.get("status", "")
    q = Payment.query.join(Booking, Payment.booking_id == Booking.booking_id)
    if status_f in ("Pending", "Paid", "Refunded"):
        q = q.filter(Payment.status == status_f)

    def total(status):
        return db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.status == status).scalar() or 0

    summary = {
        "paid": total("Paid"), "pending": total("Pending"), "refunded": total("Refunded"),
        "pending_count": Payment.query.filter_by(status="Pending").count(),
    }
    return render_template(
        "admin/payments.html", payments=q.order_by(Payment.payment_id.desc()).all(),
        summary=summary, status_f=status_f,
    )


@bp.route("/payments/<int:payment_id>/<action>", methods=["POST"])
@staff_required
def payment_action(payment_id, action):
    actions = {
        "mark-paid": (PaymentManager.mark_paid, "marked as paid"),
        "refund": (PaymentManager.refund, "refunded"),
    }
    if action not in actions:
        abort(404)
    payment = db.get_or_404(Payment, payment_id)
    handler, done = actions[action]
    staff = AuthService.current_user().staff
    _flash_result(handler(payment, staff), f"Payment #{payment.payment_id} {done}.")
    return redirect(url_for("admin.payments"))


# ---------------- A7: staff management (ADMIN only) ----------------
@bp.route("/staff")
@admin_required
def staff():
    return render_template(
        "admin/staff.html", staff_list=Staff.query.order_by(Staff.staff_id).all(),
        roles=StaffManager.ROLES,
    )


@bp.route("/staff/add", methods=["POST"])
@admin_required
def add_staff():
    member, errors = StaffManager.create(request.form)
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        flash(f"{member.full_name} added as {member.user.role}.", "success")
    return redirect(url_for("admin.staff"))


@bp.route("/staff/<int:staff_id>/edit", methods=["POST"])
@admin_required
def edit_staff(staff_id):
    member = db.get_or_404(Staff, staff_id)
    errors = StaffManager.update(member, request.form, AuthService.current_user())
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        flash(f"{member.full_name} updated.", "success")
    return redirect(url_for("admin.staff"))


@bp.route("/staff/<int:staff_id>/toggle", methods=["POST"])
@admin_required
def toggle_staff(staff_id):
    member = db.get_or_404(Staff, staff_id)
    error = StaffManager.toggle_active(member, AuthService.current_user())
    _flash_result(error, f"{member.full_name} has been "
                         f"{'activated' if member.user.is_active else 'deactivated'}.")
    return redirect(url_for("admin.staff"))


# ---------------- A8: reports ----------------
def _csv_safe(value):
    """Stop spreadsheet programs treating text as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _csv_response(result, start, end, key):
    def fmt(value, kind):
        if kind == "money":
            return f"{value:.2f}"
        if kind == "pct":
            return f"{value:.1f}%"
        return _csv_safe(value)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([result["title"], f"{start} to {end}"])
    writer.writerow([label for label, _ in result["columns"]])
    for row in result["rows"]:
        writer.writerow([fmt(v, col[1]) for v, col in zip(row, result["columns"])])
    writer.writerow([])
    for label, value, kind in result["summary"]:
        writer.writerow([label.strip(), fmt(value, kind)])
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={key}_report_{start}_to_{end}.csv"},
    )


@bp.route("/reports")
@staff_required
def reports():
    today = date.today()
    form = {
        "type": request.args.get("type", "revenue"),
        "start": request.args.get("start", (today - timedelta(days=29)).isoformat()),
        "end": request.args.get("end", today.isoformat()),
    }
    result = None

    if "type" in request.args:  # the form was submitted
        report_cls = REPORTS.get(form["type"])
        start = BookingManager.parse_date(form["start"])
        end = BookingManager.parse_date(form["end"])
        if not report_cls:
            flash("Choose a valid report type.", "danger")
        elif not start or not end:
            flash("Please enter valid start and end dates.", "danger")
        elif end < start:
            flash("The end date cannot be before the start date.", "danger")
        elif (end - start).days > 366:
            flash("The date range cannot exceed one year.", "danger")
        else:
            result = report_cls().generate(start, end)
            if request.args.get("export"):
                return _csv_response(result, start, end, form["type"])

    return render_template(
        "admin/reports.html", form=form, result=result,
        report_types=[(key, cls.label) for key, cls in REPORTS.items()],
    )