"""Tareas programadas. Cada una abre su propio contexto de aplicación."""
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models import Alert, District, Reading, User
from app.services import air, alerts, openmeteo

log = logging.getLogger("worker")


def refresh(app):
    """Refresca la caché de Open-Meteo y guarda el histórico del día."""
    with app.app_context():
        forecast = openmeteo.get_forecast(app.config["CACHE_TTL_SECONDS"], force=True)
        if not forecast:
            log.warning("refresh: sin datos")
            return
        n = air.store_history(forecast, District.query.all())
        log.info("refresh: caché actualizada, %s filas de histórico", n)


def backfill(app, days: int = 30):
    """Rellena el histórico con datos reales pasados si todavía hay poco (primer arranque)."""
    with app.app_context():
        if Reading.query.count() >= 19 * 7:
            return
        districts = District.query.order_by(District.id).all()
        try:
            data = openmeteo.fetch_remote(districts, past_days=days, forecast_days=1)
        except Exception as exc:  # no impedir el arranque del worker
            log.warning("backfill falló: %s", exc)
            return
        log.info("backfill: %s filas", air.store_history(data, districts))


def send_alerts(app):
    with app.app_context():
        token = app.config["TELEGRAM_TOKEN"]
        if not token:
            return
        forecast = openmeteo.get_forecast(app.config["CACHE_TTL_SECONDS"])
        if not forecast:
            return
        n = alerts.run_alerts(forecast, lambda chat, text: alerts.send_telegram(token, chat, text), app.config["APP_URL"])
        log.info("alertas: %s enviadas", n)


def wait_for_schema(app, timeout: int = 300):
    """El servicio web aplica las migraciones al arrancar; el worker espera a que existan los distritos."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with app.app_context():
            try:
                if District.query.count() > 0:
                    return True
            except Exception:
                pass
        time.sleep(10)
    return False


def simulate_alert(app, email: str | None = None) -> str:
    """Envía UN aviso de polen simulado («mañana, gramíneas muy altas») a un usuario con Telegram vinculado.

    No guarda nada en la base de datos (el aviso es transitorio), así que no interfiere con los avisos reales.
    """
    with app.app_context():
        token = app.config["TELEGRAM_TOKEN"]
        if not token:
            return "Falta TELEGRAM_TOKEN en este servicio."
        query = User.query.filter(User.telegram_chat_id.isnot(None))
        user = (query.filter_by(email=email) if email else query).first()
        if user is None:
            return "No hay ningún usuario con Telegram vinculado."
        district = user.favorites[0].district if user.favorites else District.query.order_by(District.id).first()
        tomorrow = datetime.now(ZoneInfo(openmeteo.TZ)).date() + timedelta(days=1)
        # previsión sintética: mañana, 200 granos/m³ de gramíneas (nivel «muy alto»)
        times = [f"{tomorrow.isoformat()}T{h:02d}:00" for h in range(24)]
        hourly = {"time": times, **{k: [0.0] * 24 for k in ("eaqi", "aqi_pm10", "aqi_pm2_5", "aqi_no2", "aqi_o3",
                                                              "pm10", "pm2_5", "no2", "o3", "olive", "birch", "alder", "mugwort", "ragweed")},
                  "grass": [200.0] * 24}
        day = air.summarize(hourly, list(range(24)))
        alert = Alert(user_id=user.id, district=district, kind="pollen", pollen_type="grass", min_level=2)  # sin session.add
        level = alerts.alert_level(alert, day)
        if level is None or level < alert.min_level:
            return "La simulación no alcanza el umbral (error de lógica)."
        text = "🧪 SIMULACIÓN (solo una vez)\n" + alerts.message_for(alert, level, tomorrow, app.config["APP_URL"])
        ok = alerts.send_telegram(token, user.telegram_chat_id, text)
        return f"Aviso simulado {'enviado' if ok else 'NO enviado'} a {user.email} ({district.name})."
