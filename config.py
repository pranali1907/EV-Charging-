import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
    APP_NAME = "ChargeLive"
    ENVIRONMENT = os.getenv("FLASK_ENV", "development")
    PORT = os.getenv("PORT", "5000")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        # Ensure psycopg2 is explicitly defined in URI if not specified
        if "postgresql+psycopg2" not in DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
            DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
        DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")
        DATABASE_NAME = os.getenv("DATABASE_NAME", "chargelive_db")
        DATABASE_USER = os.getenv("DATABASE_USER", "postgres")
        DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
        DATABASE_USER_ENCODED = quote_plus(DATABASE_USER)
        DATABASE_PASSWORD_ENCODED = quote_plus(DATABASE_PASSWORD)

        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg2://{DATABASE_USER_ENCODED}:{DATABASE_PASSWORD_ENCODED}"
            f"@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "connect_args": {
            "connect_timeout": 5,
        },
    }
