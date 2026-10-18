"""Tareas programadas. Cada una abre su propio contexto de aplicación."""
import logging
import time

from app.models import District, Reading
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
