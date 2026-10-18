from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask_login import current_user

from ..models import POLLEN_KINDS, Alert, District, Favorite, Reading
from ..services import advice, air, levels, openmeteo

bp = Blueprint("main", __name__)

WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
POLLUTANT_UNITS = "µg/m³"


def forecast_data():
    return openmeteo.get_forecast(current_app.config["CACHE_TTL_SECONDS"])


def aqi_info(eaqi):
    idx = levels.aqi_level(eaqi)
    if idx is None:
        return {"idx": None, "label": "Sin datos", "color": "#b9b4a8"}
    return {"idx": idx, "label": levels.AQI_LABELS[idx], "color": levels.AQI_COLORS[idx]}


def pollen_rows(pollen: dict):
    rows = []
    for kind in POLLEN_KINDS:
        v = pollen.get(kind)
        idx = levels.pollen_level(kind, v)
        rows.append({
            "kind": kind, "name": levels.POLLEN_NAMES[kind], "value": v, "idx": idx,
            "label": "Sin datos" if idx is None else levels.POLLEN_LABELS[idx],
            "color": "#b9b4a8" if idx is None else levels.POLLEN_COLORS[idx],
        })
    return rows


def day_label(d: date, today: date) -> str:
    if d == today:
        return "Hoy"
    if (d - today).days == 1:
        return "Mañana"
    return f"{WEEKDAYS[d.weekday()].capitalize()} {d.day}"


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/barrios")
def districts():
    forecast = forecast_data()
    items = []
    for d in District.query.order_by(District.name).all():
        cur = air.current(forecast[d.slug]) if forecast and d.slug in forecast else None
        items.append({"d": d, "aqi": aqi_info(cur["eaqi"] if cur else None), "cur": cur})
    return render_template("districts.html", items=items)


@bp.get("/api/map")
def api_map():
    forecast = forecast_data()
    out = []
    for d in District.query.order_by(District.id).all():
        cur = air.current(forecast[d.slug]) if forecast and d.slug in forecast else None
        info = aqi_info(cur["eaqi"] if cur else None)
        out.append({
            "slug": d.slug, "name": d.name, "lat": d.lat, "lon": d.lon,
            "eaqi": cur["eaqi"] if cur else None, "label": info["label"], "color": info["color"],
            "dominant": levels.POLLUTANT_NAMES.get(cur["dominant"]) if cur else None,
        })
    return jsonify(districts=out, available=forecast is not None)


@bp.get("/barrio/<slug>")
def district(slug):
    d = District.query.filter_by(slug=slug).first_or_404()
    forecast = forecast_data()
    hourly = forecast.get(slug) if forecast else None
    ctx = {"d": d, "available": hourly is not None}
    if hourly:
        today = datetime.now(ZoneInfo(openmeteo.TZ)).date()
        cur = air.current(hourly)
        pollen = pollen_rows(cur["pollen"])
        top_pollen = air.max_pollen_level(cur["pollen"])
        days = [x for x in air.daily_summaries(hourly) if x["date"] >= today]
        ctx.update(
            cur=cur, aqi=aqi_info(cur["eaqi"]), pollen=pollen,
            dominant=levels.POLLUTANT_NAMES.get(cur["dominant"]),
            pollutants=[{"name": levels.POLLUTANT_NAMES[k], "value": cur[k]} for k in levels.POLLUTANT_NAMES],
            advice=advice.advice(levels.aqi_level(cur["eaqi"]), top_pollen),
            has_pollen=any(r["value"] is not None for r in pollen),
            days=[{
                "label": day_label(x["date"], today), "aqi": aqi_info(x["eaqi"]), "eaqi": x["eaqi"],
                "pollen": {r["kind"]: r for r in pollen_rows(x["pollen"])},
            } for x in days],
        )
    is_fav, alerts = False, []
    if current_user.is_authenticated:
        is_fav = Favorite.query.filter_by(user_id=current_user.id, district_id=d.id).first() is not None
        alerts = Alert.query.filter_by(user_id=current_user.id, district_id=d.id).all()
    return render_template("district.html", is_fav=is_fav, alerts=alerts,
                           pollen_names=levels.POLLEN_NAMES, **ctx)


@bp.get("/api/district/<slug>/history")
def api_history(slug):
    d = District.query.filter_by(slug=slug).first_or_404()
    days = min(max(request.args.get("days", 30, type=int), 1), 365)
    rows = (Reading.query.filter_by(district_id=d.id).order_by(Reading.date.desc()).limit(days).all())[::-1]
    return jsonify(
        dates=[r.date.isoformat() for r in rows],
        eaqi=[r.eaqi for r in rows], pm10=[r.pm10 for r in rows], pm2_5=[r.pm2_5 for r in rows],
        no2=[r.no2 for r in rows], o3=[r.o3 for r in rows],
        pollen={k: [getattr(r, f"{k}_pollen") for r in rows] for k in POLLEN_KINDS},
        pollen_names=levels.POLLEN_NAMES,
        aqi_bounds=levels.AQI_BOUNDS, aqi_colors=levels.AQI_COLORS,
    )
