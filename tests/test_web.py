import pytest

from app import create_app
from app.extensions import db
from app.models import Alert, District, TelegramLinkCode, User, utcnow
from app.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.services import openmeteo, telegram_link
from conftest import make_hourly
from datetime import datetime
from zoneinfo import ZoneInfo


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    """Sin red: la 'API' devuelve datos sintéticos de hoy y mañana para todos los distritos."""
    today = datetime.now(ZoneInfo("Europe/Madrid")).date()
    day = f"{today.year}-{today.month:02d}-{today.day:02d}"
    # dos días desde hoy; si hoy es fin de mes, 'make_hourly' no genera fechas válidas, así que lo construimos aquí
    from datetime import timedelta
    times = [f"{(today + timedelta(days=d)).isoformat()}T{h:02d}:00" for d in range(3) for h in range(24)]
    n = len(times)
    base = make_hourly(eaqi=[45.0] * n, aqi_no2=[50.0] * n, grass=[None] * 24 + [60.0] * 24 + [200.0] * 24)
    base["time"] = times
    for k in base:
        if k != "time" and len(base[k]) != n:
            base[k] = (base[k] * 3)[:n]
    monkeypatch.setattr(openmeteo, "fetch_remote", lambda districts, client=None, **kw: {d.slug: base for d in districts})
    monkeypatch.setattr(openmeteo, "_last_attempt", 0.0)


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/entrar", data={"email": email, "password": password}, follow_redirects=True)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json["status"] == "ok"


def test_map_api_and_pages(client):
    data = client.get("/api/map").json
    assert data["available"] and len(data["districts"]) == 19
    assert data["districts"][0]["label"] == "Moderada" and data["districts"][0]["dominant"] == "NO₂"
    assert client.get("/").status_code == 200
    assert client.get("/barrios").status_code == 200
    page = client.get("/barrio/ciutat-vella").get_data(as_text=True)
    assert "Ciutat Vella" in page and "Moderada" in page and "Muy alto" in page
    assert client.get("/barrio/no-existe").status_code == 404


def test_login_demo_and_wrong_password(client):
    assert "Correo o contraseña incorrectos" in login(client, password="mal").get_data(as_text=True)
    assert "Mi cuenta" in login(client).get_data(as_text=True)


def test_login_next_is_not_open_redirect(client):
    r = client.post("/entrar?next=//evil.com", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.headers["Location"] == "/"


def test_register_validates_and_hashes(client, app):
    bad = client.post("/registro", data={"email": "x", "password": "corta", "confirm": "otra"})
    assert "Correo no válido" in bad.get_data(as_text=True)
    ok = client.post("/registro", data={"email": "Nuevo@Test.com", "password": "clave-larga-1", "confirm": "clave-larga-1"})
    assert ok.status_code == 302
    u = User.query.filter_by(email="nuevo@test.com").one()
    assert u.password_hash != "clave-larga-1" and u.check_password("clave-larga-1")
    client.post("/salir")
    dup = client.post("/registro", data={"email": "nuevo@test.com", "password": "clave-larga-1", "confirm": "clave-larga-1"})
    assert "Ya existe" in dup.get_data(as_text=True)


def test_alert_levels_map_to_each_scale(client, app):
    login(client)
    cv = District.query.filter_by(slug="ciutat-vella").one()
    client.post("/alertas", data={"district_id": cv.id, "target": "aqi", "min_level": 2})
    client.post("/alertas", data={"district_id": cv.id, "target": "olive", "min_level": 3})
    assert client.post("/alertas", data={"district_id": cv.id, "target": "xx", "min_level": 3}).status_code == 400
    kinds = {(a.kind, a.pollen_type): a.min_level for a in Alert.query.filter_by(district_id=cv.id)}
    assert kinds[("aqi", None)] == 3  # «alto» del formulario = «Mala» en el EAQI
    assert kinds[("pollen", "olive")] == 3
    # los avisos de otro usuario no se pueden borrar


def test_csrf_enforced():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite://", "SQLALCHEMY_ENGINE_OPTIONS": {}, "SECRET_KEY": "t", "TESTING": True})
    with app.app_context():
        db.create_all()
        c = app.test_client()
        r = c.post("/entrar", data={"email": "a@b.co", "password": "x"})
        assert r.status_code == 400


def test_telegram_link_code_flow(app):
    user = User.query.filter_by(email=DEMO_EMAIL).one()
    code = telegram_link.create_code(user)
    assert telegram_link.consume_code("zzzz", 1) is None
    assert telegram_link.consume_code(code.lower(), 777).id == user.id
    assert user.telegram_chat_id == 777
    assert telegram_link.consume_code(code, 777) is None  # un solo uso
    expired = telegram_link.create_code(user)
    row = db.session.get(TelegramLinkCode, expired)
    row.expires_at = utcnow().replace(year=2000)
    db.session.commit()
    assert telegram_link.consume_code(expired, 888) is None
    assert user.telegram_chat_id == 777


def test_proxy_headers_and_prod_security():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite://", "SQLALCHEMY_ENGINE_OPTIONS": {}, "TESTING": True,
                      "IS_PROD": True, "TRUSTED_PROXIES": 2, "SESSION_COOKIE_SECURE": True, "SECRET_KEY": "t"})
    with app.app_context():
        db.create_all()

        @app.get("/_ip")
        def _ip():
            from flask import request
            return f"{request.remote_addr}|{request.scheme}"

        c = app.test_client()
        # sin X-Forwarded-Proto https en producción: redirige a https
        assert c.get("/_ip").status_code == 301
        r = c.get("/_ip", headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "9.9.9.9, 10.0.0.1",
                                   "CF-Connecting-IP": "203.0.113.7"})
        assert r.get_data(as_text=True) == "203.0.113.7|https"
        assert "max-age" in r.headers["Strict-Transport-Security"]
        assert c.get("/health").status_code == 200  # el healthcheck nunca redirige
        r = c.get("/_ip", headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "9.9.9.9, 10.0.0.1"})
        assert r.get_data(as_text=True).startswith("9.9.9.9")  # sin CF: segundo salto de confianza
