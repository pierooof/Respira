from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import District, Reading
from app.services import air
from conftest import make_hourly

NOW = datetime(2026, 10, 18, 14, 30, tzinfo=ZoneInfo("Europe/Madrid"))


def test_current_picks_local_hour():
    h = make_hourly(eaqi=[i for i in range(48)], aqi_pm10=[1] * 48, aqi_no2=[30] * 48)
    cur = air.current(h, NOW)
    assert cur["eaqi"] == 14  # la posición 14 es las 14:00 del día 18
    assert cur["dominant"] == "no2"


def test_daily_summaries_use_max_and_keep_none():
    grass = [None] * 24 + [5.0] * 12 + [200.0] * 12
    h = make_hourly(grass=grass)
    d1, d2 = air.daily_summaries(h)
    assert d1["pollen"]["grass"] is None  # fuera de temporada: sin dato, no cero
    assert d2["pollen"]["grass"] == 200.0
    assert air.max_pollen_level(d2["pollen"]) == 3


def test_store_history_only_elapsed_hours_and_upserts(app):
    d = District.query.first()
    h = make_hourly(eaqi=[10] * 14 + [90] * 10 + [50] * 24)  # a partir de las 14h de hoy sube a 90
    forecast = {d.slug: h}
    air.store_history(forecast, [d], NOW)
    today = Reading.query.filter_by(district_id=d.id).order_by(Reading.date).all()
    assert [r.date.isoformat() for r in today] == ["2026-10-18"]  # el futuro no se guarda
    assert today[0].eaqi == 90  # incluye la hora 14 (la 15 en adelante no)
    air.store_history(forecast, [d], NOW)  # idempotente
    assert Reading.query.count() == 1
