"""Códigos de vinculación web ↔ Telegram (un solo uso, caducan a los 15 min)."""
import secrets
from datetime import timedelta

from ..extensions import db
from ..models import TelegramLinkCode, User, utcnow

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin 0/O/1/I/L para evitar confusiones
TTL = timedelta(minutes=15)


def create_code(user: User) -> str:
    TelegramLinkCode.query.filter_by(user_id=user.id).delete()
    code = "".join(secrets.choice(ALPHABET) for _ in range(8))
    db.session.add(TelegramLinkCode(code=code, user_id=user.id, expires_at=utcnow() + TTL))
    db.session.commit()
    return code


def consume_code(code: str, chat_id: int) -> User | None:
    """Vincula `chat_id` al usuario dueño del código. None si no existe o caducó."""
    row = db.session.get(TelegramLinkCode, (code or "").strip().upper())
    if row is None:
        return None
    expired = row.expires_at < utcnow()
    user = db.session.get(User, row.user_id)
    db.session.delete(row)  # de un solo uso, también si caducó
    if expired or user is None:
        db.session.commit()
        return None
    # un chat solo puede estar vinculado a una cuenta
    User.query.filter(User.telegram_chat_id == chat_id, User.id != user.id).update({"telegram_chat_id": None})
    user.telegram_chat_id = chat_id
    db.session.commit()
    return user
