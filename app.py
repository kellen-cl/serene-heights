from datetime import date

from flask import Flask, render_template

from config import Config
from extensions import db

HOTEL_NAME = "Serene Heights"
CURRENCY = "$"

# Room photos are chosen by room type (the rooms table has no image column)
ROOM_IMAGES = {
    "Single": "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=900&q=80",
    "Double": "https://images.unsplash.com/photo-1618773928121-c32242e63f39?auto=format&fit=crop&w=900&q=80",
    "Suite": "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=900&q=80",
}
FALLBACK_IMAGE = "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=900&q=80"

ERROR_PAGES = {
    404: ("Page not found", "The page you are looking for does not exist or has moved."),
    405: ("Action not allowed", "That action is not available from this link. Please use the buttons on the page."),
    500: ("Something went wrong", "An unexpected error occurred. Please try again, or contact the front desk."),
}


def room_image(room_type):
    return ROOM_IMAGES.get(room_type, FALLBACK_IMAGE)


def _register_error_handlers(app):
    for code, (title, message) in ERROR_PAGES.items():
        def handler(error, code=code, title=title, message=message):
            if code == 500:
                db.session.rollback()
            return render_template("errors/error.html", code=code, title=title, message=message), code
        app.register_error_handler(code, handler)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    import models  # noqa: F401  (registers all tables)
    from routes.guest import bp as guest_bp
    from routes.admin import bp as admin_bp
    from services.auth_service import AuthService

    app.register_blueprint(guest_bp)
    app.register_blueprint(admin_bp)

    app.jinja_env.globals["room_image"] = room_image
    app.jinja_env.globals["fallback_image"] = FALLBACK_IMAGE

    @app.context_processor
    def inject_globals():
        return {
            "hotel_name": HOTEL_NAME,
            "currency": CURRENCY,
            "current_year": date.today().year,
            "current_user": AuthService.current_user(),
        }

    _register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    create_app().run(debug=True)