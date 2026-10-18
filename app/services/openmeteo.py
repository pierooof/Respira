"""Cliente de Open-Meteo Air Quality con caché en BD y control de frecuencia.

Una sola petición trae los 19 distritos (la API admite varias coordenadas), y el
resultado se cachea `CACHE_TTL_SECONDS`. El plan gratuito permite 600 llamadas/min
y 5000/h; con una por hora estamos muy por debajo.
"""
import logging
import time

import httpx
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import ApiCache, District, utcnow

log = logging.getLogger(__name__)

API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TZ = "Europe/Madrid"
CACHE_KEY = "forecast:valencia"
MIN_RETRY_SECONDS = 60  # no machacar la API si falla

# nombre en la API -> nombre interno
HOURLY = {
    "european_aqi": "eaqi",
    "european_aqi_pm10": "aqi_pm10",
    "european_aqi_pm2_5": "aqi_pm2_5",
    "european_aqi_no2": "aqi_no2",
    "european_aqi_o3": "aqi_o3",
    "pm10": "pm10",
    "pm2_5": "pm2_5",
    "nitrogen_dioxide": "no2",
    "ozone": "o3",
    "grass_pollen": "grass",
    "olive_pollen": "olive",
    "birch_pollen": "birch",
    "alder_pollen": "alder",
    "mugwort_pollen": "mugwort",
    "ragweed_pollen": "ragweed",
}

_last_attempt = 0.0


def fetch_remote(districts, client=None) -> dict:
    """Devuelve {slug: {'time': [...], 'eaqi': [...], ...}} (past_days=1 + 5 días de previsión)."""
    params = {
        "latitude": ",".join(str(d.lat) for d in districts),
        "longitude": ",".join(str(d.lon) for d in districts),
        "hourly": ",".join(HOURLY),
        "past_days": 1,
        "forecast_days": 5,
        "timezone": TZ,
    }
    resp = (client or httpx).get(API_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):  # con una sola coordenada la API devuelve un objeto
        data = [data]
    if len(data) != len(districts):
        raise ValueError("Open-Meteo devolvió un nº de ubicaciones inesperado")
    out = {}
    for d, loc in zip(districts, data):
        h = loc["hourly"]
        out[d.slug] = {"time": h["time"], **{internal: h.get(api) for api, internal in HOURLY.items()}}
    return out


def get_forecast(ttl: int, force: bool = False, client=None) -> dict | None:
    """Previsión cacheada. Si la API falla devuelve la caché caducada (o None si no hay nada)."""
    global _last_attempt
    row = db.session.get(ApiCache, CACHE_KEY)
    if row and not force and (utcnow() - row.fetched_at).total_seconds() < ttl:
        return row.payload
    if time.monotonic() - _last_attempt < MIN_RETRY_SECONDS:
        return row.payload if row else None
    _last_attempt = time.monotonic()
    try:
        data = fetch_remote(District.query.order_by(District.id).all(), client)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("Open-Meteo no disponible: %s", exc)
        return row.payload if row else None
    try:
        db.session.merge(ApiCache(key=CACHE_KEY, payload=data, fetched_at=utcnow()))
        db.session.commit()
    except IntegrityError:  # otro proceso guardó a la vez
        db.session.rollback()
    return data
