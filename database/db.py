from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate()


def init_database(app):
    """Initialize database extensions once for the Flask app factory."""
    db.init_app(app)
    migrate.init_app(app, db)


def test_database_connection():
    """Check PostgreSQL availability without stopping the Flask application."""
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        print("\n==================================")
        print("Connected to PostgreSQL Successfully")
        print("==================================\n")
    except OperationalError as error:
        print("\n==================================")
        print("PostgreSQL Connection Failed")
        print("==================================")
        print(_format_operational_error(error))
        print("==================================\n")
    except SQLAlchemyError as error:
        print("\n==================================")
        print("Database Configuration Error")
        print("==================================")
        print(str(error))
        print("==================================\n")


def _format_operational_error(error):
    message = str(error.orig) if getattr(error, "orig", None) else str(error)
    lowered_message = message.lower()

    if "password authentication failed" in lowered_message:
        return "Wrong PostgreSQL password. Check DATABASE_PASSWORD in .env."

    if "no password supplied" in lowered_message:
        return "No PostgreSQL password supplied. Set DATABASE_PASSWORD in .env."

    if "database" in lowered_message and "does not exist" in lowered_message:
        return "Wrong database name. Check DATABASE_NAME or create chargelive_db."

    if "connection refused" in lowered_message:
        return "PostgreSQL server is not running or is not accepting connections."

    if "timeout" in lowered_message or "timed out" in lowered_message:
        return "PostgreSQL connection timed out. Check host, port, and server status."

    return f"Unable to connect to PostgreSQL. Details: {message}"
