from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import Alert, District, User
from app.seed import DEMO_EMAIL
from app.services import alerts
from conftest import make_hourly

NOW = datetime(2026, 10, 18, 19, 0, tzinfo=ZoneInfo("Europe/Madrid"))


def _forecast(slug, tomorrow_grass):
    h = make_hourly(grass=[5.0] * 24 + [tomorrow_grass] * 24)
    return {slug: h}


def _setup():
    user = User.query.filter_by(email=DEMO_EMAIL).one()
    user.telegram_chat_id = 42
    alert = Alert.query.filter_by(user_id=user.id, kind="pollen", pollen_type="grass").one()  # alto (2) en Ciutat Vella
    db.session.commit()
    return alert


def test_alert_sent_once_when_threshold_reached(app):
    alert = _setup()
    sent = []
    send = lambda chat, text: sent.append((chat, text)) or True
    fc = _forecast("ciutat-vella", 80.0)  # gramíneas «alto» (50–150)
    assert alerts.run_alerts(fc, send, "https://x.test", NOW) == 1
    chat, text = sent[0]
    assert chat == 42 and "gramíneas" in text and "alto" in text and "https://x.test/barrio/ciutat-vella" in text
    assert alert.last_notified_for == (NOW + timedelta(days=1)).date()
    assert alerts.run_alerts(fc, send, "https://x.test", NOW) == 0  # no se repite el mismo día objetivo


def test_no_alert_below_threshold_or_unlinked_or_failed_send(app):
    alert = _setup()
    assert alerts.run_alerts(_forecast("ciutat-vella", 20.0), lambda c, t: True, "u", NOW) == 0  # solo «moderado»
    assert alerts.run_alerts(_forecast("ciutat-vella", 80.0), lambda c, t: False, "u", NOW) == 0  # envío fallido
    assert alert.last_notified_for is None  # se reintentará
    User.query.filter_by(email=DEMO_EMAIL).one().telegram_chat_id = None
    db.session.commit()
    assert alerts.run_alerts(_forecast("ciutat-vella", 80.0), lambda c, t: True, "u", NOW) == 0


def test_simulate_alert_sends_once_without_persisting(app, monkeypatch):
    from worker import jobs
    sent = []
    monkeypatch.setattr(jobs.alerts, "send_telegram", lambda token, chat, text: sent.append((chat, text)) or True)
    assert "Falta TELEGRAM_TOKEN" in jobs.simulate_alert(app)
    app.config["TELEGRAM_TOKEN"] = "1:T"
    assert "No hay ningún usuario" in jobs.simulate_alert(app)
    _setup()  # vincula al usuario demo (chat 42)
    before = Alert.query.count()
    assert "enviado" in jobs.simulate_alert(app, DEMO_EMAIL)
    chat, text = sent[0]
    assert chat == 42 and "SIMULACIÓN" in text and "gramíneas" in text and "muy alto" in text
    assert Alert.query.count() == before  # nada persistido
    assert all(a.last_notified_for is None for a in Alert.query.all())
