"""Configuración leída solo de variables de entorno."""
import os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote


def database_url() -> str:
    """Construye la URL SQLAlchemy a partir de MYSQL_URL o de las MYSQL* de Railway."""
    url = os.getenv("MYSQL_URL")
    if not url:
        host = os.getenv("MYSQLHOST", "127.0.0.1")
        port = os.getenv("MYSQLPORT", "3306")
        user = quote(os.getenv("MYSQLUSER", "respira"), safe="")
        pwd = quote(os.getenv("MYSQLPASSWORD", ""), safe="")
        name = os.getenv("MYSQLDATABASE", "respira")
        url = f"mysql://{user}:{pwd}@{host}:{port}/{name}"
    # SQLAlchemy necesita el driver explícito
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.setdefault("charset", "utf8mb4")
    return urlunsplit(parts._replace(query=urlencode(query)))


class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    IS_PROD = APP_ENV == "production"
    APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret")
    TRUSTED_PROXIES = int(os.getenv("TRUSTED_PROXIES", "1"))

    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # Cookies: HttpOnly + Lax siempre; Secure solo en producción (en local se usa http)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PROD
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = IS_PROD
    PREFERRED_URL_SCHEME = "https" if IS_PROD else "http"

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    REFRESH_MINUTES = int(os.getenv("REFRESH_MINUTES", "60"))
