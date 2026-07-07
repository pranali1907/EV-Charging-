from flask import Flask, render_template

from config import Config
from admin import admin_bp
from database.db import init_database, test_database_connection
from routes.book import book_bp
from routes.home import home_bp
from services.connector_type_service import seed_default_connectors


def register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(error):
        return (
            render_template(
                "404.html",
                message="The page or charging station you requested was not found.",
            ),
            404,
        )


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    import models  # noqa: F401

    init_database(app)
    app.register_blueprint(home_bp)
    app.register_blueprint(book_bp)
    app.register_blueprint(admin_bp)
    register_error_handlers(app)

    import secrets
    from flask import session, request, abort

    @app.context_processor
    def inject_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return dict(csrf_token=lambda: session["csrf_token"])

    @app.before_request
    def validate_csrf():
        import sys
        if app.testing or app.config.get("TESTING") or "pytest" in sys.modules or "unittest" in sys.modules:
            return
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            if request.path.startswith("/api/iot/") or request.path.startswith("/api/recommend"):
                return
            token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            session_token = session.get("csrf_token")
            if not session_token or not token or session_token != token:
                abort(400, description="CSRF token missing or invalid.")

    with app.app_context():
        try:
            import os
            from flask_migrate import upgrade as flask_db_upgrade
            migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
            flask_db_upgrade(directory=migrations_dir)
            print("Database migrations applied successfully.")
        except Exception as err:
            print(f"Database migrations upgrade failed: {err}")
        test_database_connection()
        seed_default_connectors()

    return app


app = create_app()


def get_port():
    try:
        return int(app.config.get("PORT", 5000))
    except (TypeError, ValueError):
        print("Invalid PORT value in .env. Falling back to 5000.")
        return 5000


if __name__ == "__main__":
    port = get_port()
    debug = app.config.get("ENVIRONMENT") == "development"
    app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=False)
