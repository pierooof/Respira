"""El bot se prueba llamando a sus manejadores con mensajes simulados (sin red ni token real)."""
import asyncio
from types import SimpleNamespace

from app.extensions import db
from app.models import User
from app.seed import DEMO_EMAIL
from app.services import openmeteo, telegram_link
from worker import bot as worker_bot
from conftest import make_hourly


def _call(application, command, chat_id, args=()):
    replies = []

    async def reply_text(text, **kw):
        replies.append(text)

    update = SimpleNamespace(message=SimpleNamespace(reply_text=reply_text), effective_chat=SimpleNamespace(id=chat_id))
    ctx = SimpleNamespace(args=list(args))
    for handler in application.handlers[0]:
        if command in handler.commands:
            asyncio.run(handler.callback(update, ctx))
            return replies
    raise AssertionError(f"sin manejador para /{command}")


def test_bot_link_status_unlink(app, monkeypatch):
    app.config["TELEGRAM_TOKEN"] = "123456:TEST"
    monkeypatch.setattr(openmeteo, "get_forecast", lambda ttl, **kw: {
        d: make_hourly(day="2026-10-18", eaqi=[44.0] * 48) for d in ("ciutat-vella", "benimaclet")})
    application = worker_bot.build(app)
    user = User.query.filter_by(email=DEMO_EMAIL).one()

    assert "vincular" in _call(application, "start", 5)[0].lower()
    assert "Uso:" in _call(application, "vincular", 5)[0]
    assert "no válido" in _call(application, "vincular", 5, ["MALCODIG"])[0]
    assert "no has vinculado" in _call(application, "estado", 5)[0].lower()

    code = telegram_link.create_code(user)
    assert "vinculada" in _call(application, "vincular", 5, [code])[0]
    db.session.refresh(user)
    assert user.telegram_chat_id == 5

    estado = _call(application, "estado", 5)[0]
    assert "Ciutat Vella" in estado and "Benimaclet" in estado and "Moderada" in estado

    assert "desvinculada" in _call(application, "desvincular", 5)[0].lower()
    db.session.refresh(user)
    assert user.telegram_chat_id is None

