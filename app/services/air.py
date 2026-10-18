"""Interpretación de la previsión horaria: valores actuales, resumen diario, guardado del histórico."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..extensions import db
from ..models import POLLEN_KINDS, Reading
from . import levels
from .openmeteo import TZ

SUB_INDEXES = {"pm10": "aqi_pm10", "pm2_5": "aqi_pm2_5", "no2": "aqi_no2", "o3": "aqi_o3"}


def _max(values):
    vals = [v for v in values if v is not None]
    return max(vals) if vals else None


def summarize(hourly: dict, idx: list[int]) -> dict:
    """Resumen de las horas `idx`: máximo de cada magnitud. Con una sola hora es el valor puntual."""
    mx = {k: _max([hourly[k][i] for i in idx]) for k in hourly if k != "time"}
    sub = {pol: mx[key] for pol, key in SUB_INDEXES.items()}
    eaqi = mx["eaqi"]
    return {
        "eaqi": None if eaqi is None else round(eaqi),
        "dominant": levels.dominant_pollutant(sub),
        **{p: mx[p] for p in ("pm10", "pm2_5", "no2", "o3")},
        "pollen": {k: mx[k] for k in POLLEN_KINDS},
    }


def now_index(hourly: dict, now: datetime | None = None) -> int:
    """Posición de la hora actual (hora local de Valencia) en el array horario."""
    stamp = hour_stamp(now or datetime.now(ZoneInfo(TZ)))
    times = hourly["time"]
    return times.index(stamp) if stamp in times else 0


def current(hourly: dict, now: datetime | None = None) -> dict:
    return summarize(hourly, [now_index(hourly, now)])


def days(hourly: dict) -> dict[date, list[int]]:
    """Índices horarios agrupados por día."""
    out: dict[date, list[int]] = {}
    for i, t in enumerate(hourly["time"]):
        out.setdefault(date.fromisoformat(t[:10]), []).append(i)
    return out


def daily_summaries(hourly: dict) -> list[dict]:
    """Un resumen por día con su fecha, para la previsión y el histórico."""
    return [{"date": d, **summarize(hourly, idx)} for d, idx in sorted(days(hourly).items())]


def max_pollen_level(pollen: dict) -> int | None:
    lv = [levels.pollen_level(k, v) for k, v in pollen.items()]
    lv = [x for x in lv if x is not None]
    return max(lv) if lv else None


def store_history(forecast: dict, districts, now: datetime | None = None) -> int:
    """Guarda/actualiza el resumen de ayer y de hoy (hoy solo con las horas ya transcurridas)."""
    now = now or datetime.now(ZoneInfo(TZ))
    today, cur = now.date(), hour_stamp(now)
    n = 0
    for d in districts:
        hourly = forecast.get(d.slug)
        if not hourly:
            continue
        for day, idx in days(hourly).items():
            if day > today:
                continue
            if day == today:
                idx = [i for i in idx if hourly["time"][i] <= cur]
            if not idx:
                continue
            s = summarize(hourly, idx)
            row = Reading.query.filter_by(district_id=d.id, date=day).first() or Reading(district_id=d.id, date=day)
            row.eaqi, row.dominant = s["eaqi"], s["dominant"]
            row.pm10, row.pm2_5, row.no2, row.o3 = s["pm10"], s["pm2_5"], s["no2"], s["o3"]
            for k in POLLEN_KINDS:
                setattr(row, f"{k}_pollen", s["pollen"][k])
            db.session.add(row)
            n += 1
    db.session.commit()
    return n


def hour_stamp(now: datetime) -> str:
    """Marca horaria 'YYYY-MM-DDTHH:00' (comparable como texto con el array `time`)."""
    return now.strftime("%Y-%m-%dT%H:00")
