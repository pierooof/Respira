from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import POLLEN_KINDS, Alert, District, Favorite
from ..services import air, levels, telegram_link
from .main import aqi_info, forecast_data

bp = Blueprint("account", __name__)
MAX_ALERTS = 20
# El formulario usa 1..3 (moderado/alto/muy alto); en el índice EAQI equivalen a 2..4.
AQI_FROM_FORM = {1: 2, 2: 3, 3: 4}


def bot_enabled() -> bool:
    """La web solo necesita el usuario del bot (público); el token secreto vive únicamente en el worker."""
    return bool(current_app.config["TELEGRAM_BOT_USERNAME"] or current_app.config["TELEGRAM_TOKEN"])


@bp.get("/cuenta")
@login_required
def account():
    forecast = forecast_data()
    favs = []
    for f in current_user.favorites:
        cur = air.current(forecast[f.district.slug]) if forecast and f.district.slug in forecast else None
        favs.append({"d": f.district, "aqi": aqi_info(cur["eaqi"] if cur else None), "eaqi": cur["eaqi"] if cur else None})
    username = current_app.config["TELEGRAM_BOT_USERNAME"]
    return render_template(
        "account.html", favs=favs, alerts=current_user.alerts,
        bot_enabled=bot_enabled(),
        bot_url=f"https://t.me/{username}" if username else None,
        code=request.args.get("code"),
    )


@bp.post("/barrio/<slug>/favorito")
@login_required
def toggle_favorite(slug):
    d = District.query.filter_by(slug=slug).first_or_404()
    fav = Favorite.query.filter_by(user_id=current_user.id, district_id=d.id).first()
    if fav:
        db.session.delete(fav)
    else:
        db.session.add(Favorite(user_id=current_user.id, district_id=d.id))
    db.session.commit()
    return redirect(url_for("main.district", slug=slug))


@bp.post("/alertas")
@login_required
def create_alert():
    d = db.session.get(District, request.form.get("district_id", type=int) or 0)
    target = request.form.get("target", "")
    level = request.form.get("min_level", type=int)
    if d is None or level not in (1, 2, 3) or (target != "aqi" and target not in POLLEN_KINDS):
        abort(400)
    if len(current_user.alerts) >= MAX_ALERTS:
        flash(f"Has alcanzado el máximo de {MAX_ALERTS} avisos.", "error")
        return redirect(url_for("main.district", slug=d.slug))
    kind = "aqi" if target == "aqi" else "pollen"
    min_level = AQI_FROM_FORM[level] if kind == "aqi" else level
    pollen_type = None if kind == "aqi" else target
    exists = Alert.query.filter_by(user_id=current_user.id, district_id=d.id, kind=kind,
                                   pollen_type=pollen_type, min_level=min_level).first()
    if not exists:
        db.session.add(Alert(user_id=current_user.id, district_id=d.id, kind=kind,
                             pollen_type=pollen_type, min_level=min_level))
        db.session.commit()
        flash("Aviso creado." + ("" if current_user.telegram_chat_id else " Vincula Telegram para recibirlo."), "success")
    return redirect(url_for("main.district", slug=d.slug))


@bp.post("/alertas/<int:alert_id>/borrar")
@login_required
def delete_alert(alert_id):
    alert = Alert.query.filter_by(id=alert_id, user_id=current_user.id).first_or_404()
    slug = alert.district.slug
    db.session.delete(alert)
    db.session.commit()
    return redirect(request.referrer or url_for("main.district", slug=slug))


@bp.post("/telegram/codigo")
@login_required
def telegram_code():
    if not bot_enabled():
        abort(404)
    code = telegram_link.create_code(current_user)
    return redirect(url_for("account.account", code=code))


@bp.post("/telegram/desvincular")
@login_required
def telegram_unlink():
    current_user.telegram_chat_id = None
    db.session.commit()
    flash("Telegram desvinculado.", "success")
    return redirect(url_for("account.account"))
