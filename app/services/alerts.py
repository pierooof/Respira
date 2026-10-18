"""Evaluación de avisos: ¿el nivel previsto para mañana alcanza el umbral del usuario?"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from ..extensions import db
from ..models import Alert, User
from . import air, levels
from .openmeteo import TZ

log = logging.getLogger(__name__)
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def alert_level(alert: Alert, day: dict) -> int | None:
    """Nivel previsto en el resumen `day` para lo que vigila este aviso."""
    if alert.kind == "aqi":
        return levels.aqi_level(day["eaqi"])
    return levels.pollen_level(alert.pollen_type, day["pollen"][alert.pollen_type])


def message_for(alert: Alert, level: int, tomorrow, app_url: str) -> str:
    if alert.kind == "aqi":
        what, label = "la calidad del aire", levels.AQI_LABELS[level].lower()
    else:
        what, label = f"el polen de {levels.POLLEN_NAMES[alert.pollen_type].lower()}", levels.POLLEN_LABELS[level].lower()
    d = alert.district
    return (f"⚠️ Mañana {WEEKDAYS[tomorrow.weekday()]} {tomorrow.day}: {what} será {label} en {d.name}.\n"
            f"Más detalle: {app_url}/barrio/{d.slug}")


def sample_pollen_message(district, tomorrow, app_url: str) -> str:
    """Aviso de ejemplo (nivel «alto» de gramíneas) para comprobar la entrega por Telegram."""
    return (f"🧪 PRUEBA · Mañana {WEEKDAYS[tomorrow.weekday()]} {tomorrow.day}: el polen de gramíneas será alto en {district.name}.\n"
            f"Así te avisaré cuando se cumpla uno de tus avisos reales.\n"
            f"Más detalle: {app_url}/barrio/{district.slug}")


def send_telegram(token: str, chat_id: int, text: str) -> bool:
    try:
        r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                       json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=15)
        return r.status_code == 200
    except httpx.HTTPError as exc:
        log.warning("Telegram no disponible: %s", exc)
        return False


def run_alerts(forecast: dict, send, app_url: str, now: datetime | None = None) -> int:
    """Envía los avisos pendientes con `send(chat_id, text) -> bool`. Devuelve cuántos se enviaron."""
    now = now or datetime.now(ZoneInfo(TZ))
    tomorrow = now.date() + timedelta(days=1)
    sent = 0
    pending = (Alert.query.join(User).filter(User.telegram_chat_id.isnot(None))
               .filter((Alert.last_notified_for.is_(None)) | (Alert.last_notified_for != tomorrow)).all())
    summaries = {}  # resumen de mañana por distrito, calculado una vez
    for alert in pending:
        slug = alert.district.slug
        if slug not in summaries:
            hourly = forecast.get(slug)
            idx = air.days(hourly).get(tomorrow) if hourly else None
            summaries[slug] = air.summarize(hourly, idx) if idx else None
        day = summaries[slug]
        level = alert_level(alert, day) if day else None
        if level is None or level < alert.min_level:
            continue
        if send(alert.user.telegram_chat_id, message_for(alert, level, tomorrow, app_url)):
            alert.last_notified_for = tomorrow
            sent += 1
    db.session.commit()
    return sent
