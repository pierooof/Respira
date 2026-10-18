from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager
from .services import levels

POLLEN_KINDS = ("grass", "olive", "birch", "alder", "mugwort", "ragweed")


def utcnow() -> datetime:
    """UTC sin zona (así lo guarda MySQL DATETIME)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(190), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    telegram_chat_id = db.Column(db.BigInteger, unique=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    favorites = db.relationship("Favorite", cascade="all, delete-orphan", back_populates="user")
    alerts = db.relationship("Alert", cascade="all, delete-orphan", back_populates="user")

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class TelegramLinkCode(db.Model):
    """Código de un solo uso que el usuario envía al bot para vincular su cuenta."""
    __tablename__ = "telegram_link_codes"
    code = db.Column(db.String(12), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)


class District(db.Model):
    __tablename__ = "districts"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)


class Reading(db.Model):
    """Resumen diario (máximos del día) por distrito: alimenta el histórico y los gráficos."""
    __tablename__ = "readings"
    __table_args__ = (db.UniqueConstraint("district_id", "date", name="uq_reading_day"),)
    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.Integer, db.ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    eaqi = db.Column(db.Integer)
    dominant = db.Column(db.String(8))
    pm10 = db.Column(db.Float)
    pm2_5 = db.Column(db.Float)
    no2 = db.Column(db.Float)
    o3 = db.Column(db.Float)
    grass_pollen = db.Column(db.Float)
    olive_pollen = db.Column(db.Float)
    birch_pollen = db.Column(db.Float)
    alder_pollen = db.Column(db.Float)
    mugwort_pollen = db.Column(db.Float)
    ragweed_pollen = db.Column(db.Float)


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "district_id", name="uq_favorite"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    district_id = db.Column(db.Integer, db.ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    user = db.relationship("User", back_populates="favorites")
    district = db.relationship("District")


class Alert(db.Model):
    """Avisa si el nivel previsto para mañana alcanza `min_level` (kind: 'pollen' | 'aqi')."""
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    district_id = db.Column(db.Integer, db.ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    pollen_type = db.Column(db.String(10))
    min_level = db.Column(db.SmallInteger, nullable=False)
    last_notified_for = db.Column(db.Date)  # día objetivo ya avisado: evita duplicados
    user = db.relationship("User", back_populates="alerts")
    district = db.relationship("District")

    def describe(self) -> str:
        if self.kind == "aqi":
            return f"Calidad del aire: {levels.AQI_LABELS[self.min_level].lower()} o peor"
        return f"Polen de {levels.POLLEN_NAMES[self.pollen_type].lower()}: {levels.POLLEN_LABELS[self.min_level].lower()} o más"


class ApiCache(db.Model):
    """Caché compartida entre web y worker."""
    __tablename__ = "api_cache"
    key = db.Column(db.String(64), primary_key=True)
    payload = db.Column(db.JSON, nullable=False)
    fetched_at = db.Column(db.DateTime, nullable=False)
