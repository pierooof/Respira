import pytest

from app import create_app
from app.extensions import db
from app.seed import seed


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test",
    })
    with app.app_context():
        db.create_all()
        seed()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_hourly(day="2026-10-18", n_days=2, **overrides):
    """Previsión horaria sintética de un distrito (24 h por día), para tests sin red."""
    times = [f"{day[:8]}{int(day[8:]) + d:02d}T{h:02d}:00" for d in range(n_days) for h in range(24)]
    size = len(times)
    keys = ["eaqi", "aqi_pm10", "aqi_pm2_5", "aqi_no2", "aqi_o3", "pm10", "pm2_5", "no2", "o3",
            "grass", "olive", "birch", "alder", "mugwort", "ragweed"]
    data = {"time": times, **{k: [10.0] * size for k in keys}}
    data.update(overrides)
    return data
