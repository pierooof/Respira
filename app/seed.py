"""Datos iniciales: distritos de Valencia (centro aproximado) y usuario demo. Idempotente."""
from flask import current_app

from .extensions import db
from .models import Alert, District, Favorite, User

DISTRICTS = [
    ("ciutat-vella", "Ciutat Vella", 39.4745, -0.3770),
    ("l-eixample", "l'Eixample", 39.4650, -0.3630),
    ("extramurs", "Extramurs", 39.4660, -0.3900),
    ("campanar", "Campanar", 39.4900, -0.4000),
    ("la-saidia", "la Saïdia", 39.4890, -0.3790),
    ("el-pla-del-real", "el Pla del Real", 39.4780, -0.3590),
    ("l-olivereta", "l'Olivereta", 39.4660, -0.4000),
    ("patraix", "Patraix", 39.4580, -0.4000),
    ("jesus", "Jesús", 39.4500, -0.3900),
    ("quatre-carreres", "Quatre Carreres", 39.4440, -0.3660),
    ("poblats-maritims", "Poblats Marítims", 39.4650, -0.3330),
    ("camins-al-grau", "Camins al Grau", 39.4700, -0.3450),
    ("algiros", "Algirós", 39.4760, -0.3450),
    ("benimaclet", "Benimaclet", 39.4900, -0.3600),
    ("rascanya", "Rascanya", 39.4960, -0.3770),
    ("benicalap", "Benicalap", 39.4960, -0.3980),
    ("pobles-del-nord", "Pobles del Nord", 39.5300, -0.3700),
    ("pobles-de-l-oest", "Pobles de l'Oest", 39.5000, -0.4400),
    ("pobles-del-sud", "Pobles del Sud", 39.4000, -0.3300),
]

DEMO_EMAIL = "demo@respira.app"
DEMO_PASSWORD = "demo1234"


def seed():
    for slug, name, lat, lon in DISTRICTS:
        d = District.query.filter_by(slug=slug).first()
        if d is None:
            db.session.add(District(slug=slug, name=name, lat=lat, lon=lon))
        else:
            d.name, d.lat, d.lon = name, lat, lon
    db.session.flush()

    if current_app.config["DEMO_ENABLED"] and User.query.filter_by(email=DEMO_EMAIL).first() is None:
        user = User(email=DEMO_EMAIL)
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        db.session.flush()
        for slug in ("ciutat-vella", "benimaclet"):
            d = District.query.filter_by(slug=slug).one()
            db.session.add(Favorite(user_id=user.id, district_id=d.id))
        d = District.query.filter_by(slug="ciutat-vella").one()
        db.session.add(Alert(user_id=user.id, district_id=d.id, kind="pollen",
                             pollen_type="grass", min_level=2))
    db.session.commit()


def remove_demo() -> bool:
    """Borra la cuenta demo con sus favoritos y avisos. True si existía."""
    user = User.query.filter_by(email=DEMO_EMAIL).first()
    if user is None:
        return False
    db.session.delete(user)  # favoritos y avisos caen en cascada
    db.session.commit()
    return True
