import ipaddress

from flask import Flask, redirect, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, login_manager, migrate

# CSP: scripts propios + CDN de Leaflet/Chart.js; teselas del mapa de OpenStreetMap.
CSP = (
    "default-src 'self'; "
    "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://tile.openstreetmap.org https://unpkg.com; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class CloudflareIP:
    """Si Cloudflare envía CF-Connecting-IP, esa es la IP real del cliente."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        raw = environ.get("HTTP_CF_CONNECTING_IP", "").strip()
        try:
            environ["REMOTE_ADDR"] = str(ipaddress.ip_address(raw))
        except ValueError:
            pass  # cabecera ausente o basura: se conserva lo que dejó ProxyFix
        return self.app(environ, start_response)


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    if app.config["IS_PROD"] and app.config["SECRET_KEY"] == "dev-only-secret":
        raise RuntimeError("Define SECRET_KEY en producción.")

    n = app.config["TRUSTED_PROXIES"]
    if n > 0:
        # x_proto/x_host=1: nos fiamos del último salto (Railway), que sí informa del esquema real;
        # con x_proto=n, ProxyFix ignoraría una cabecera de un solo valor y habría bucle de redirección.
        app.wsgi_app = ProxyFix(CloudflareIP(app.wsgi_app), x_for=n, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    from . import models  # noqa: F401  (registra las tablas para las migraciones)

    from .blueprints import register_blueprints
    register_blueprints(app)

    from . import cli
    cli.register(app)

    @app.before_request
    def force_https():
        # Cloudflare/Railway terminan TLS; ProxyFix nos da el esquema real.
        if app.config["IS_PROD"] and request.scheme != "https" and request.path != "/health":
            return redirect(request.url.replace("http://", "https://", 1), code=301)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        if app.config["IS_PROD"]:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp

    return app
