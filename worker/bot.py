"""Bot de Telegram: /start, /vincular <código>, /estado, /probar y /desvincular."""
import asyncio
import logging

from telegram import Update
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, ContextTypes

from app.extensions import db
from app.models import District, User
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services import air, alerts, levels, openmeteo, telegram_link
from app.blueprints.main import aqi_info


def build(app) -> Application:
    token = app.config["TELEGRAM_TOKEN"]

    def vincular_sync(code, chat_id):
        with app.app_context():
            return telegram_link.consume_code(code, chat_id) is not None

    def estado_sync(chat_id):
        with app.app_context():
            user = User.query.filter_by(telegram_chat_id=chat_id).first()
            if not user:
                return None
            forecast = openmeteo.get_forecast(app.config["CACHE_TTL_SECONDS"]) or {}
            lines = []
            for f in user.favorites:
                hourly = forecast.get(f.district.slug)
                if hourly:
                    cur = air.current(hourly)
                    lines.append(f"• {f.district.name}: {cur['eaqi']} ({aqi_info(cur['eaqi'])['label']})")
            return lines

    def desvincular_sync(chat_id):
        with app.app_context():
            n = User.query.filter_by(telegram_chat_id=chat_id).update({"telegram_chat_id": None})
            db.session.commit()
            return n > 0

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Hola 👋 Soy el bot de Respira.\n\n"
            f"1. Entra en {app.config['APP_URL']}/cuenta y pulsa «Generar código».\n"
            "2. Envíame: /vincular TUCÓDIGO\n\n"
            "Después te avisaré de los niveles previstos para mañana en los barrios que elijas.\n"
            "Comandos: /estado · /probar · /desvincular")

    async def vincular(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ctx.args:
            await update.message.reply_text("Uso: /vincular TUCÓDIGO (lo generas en tu cuenta de la web).")
            return
        ok = await asyncio.to_thread(vincular_sync, ctx.args[0], update.effective_chat.id)
        await update.message.reply_text("✅ Cuenta vinculada. ¡Listo para recibir avisos!" if ok
                                        else "Código no válido o caducado. Genera uno nuevo en la web.")

    async def estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        lines = await asyncio.to_thread(estado_sync, update.effective_chat.id)
        if lines is None:
            await update.message.reply_text("Aún no has vinculado tu cuenta. Usa /start.")
        else:
            await update.message.reply_text("\n".join(["Calidad del aire ahora (EAQI):", *lines]) if lines
                                            else "No tienes barrios favoritos todavía.")

    def probar_sync(chat_id):
        """Envía un aviso de polen de ejemplo por el mismo camino que usan los avisos reales."""
        with app.app_context():
            user = User.query.filter_by(telegram_chat_id=chat_id).first()
            if not user:
                return None
            district = user.favorites[0].district if user.favorites else District.query.order_by(District.id).first()
            tomorrow = datetime.now(ZoneInfo(openmeteo.TZ)).date() + timedelta(days=1)
            text = alerts.sample_pollen_message(district, tomorrow, app.config["APP_URL"])
            return alerts.send_telegram(token, chat_id, text)

    async def probar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        ok = await asyncio.to_thread(probar_sync, update.effective_chat.id)
        if ok is None:
            await update.message.reply_text("Aún no has vinculado tu cuenta. Usa /start.")
        elif not ok:
            await update.message.reply_text("No se pudo enviar el aviso de prueba. Revisa los logs del worker.")

    async def desvincular(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        ok = await asyncio.to_thread(desvincular_sync, update.effective_chat.id)
        await update.message.reply_text("Cuenta desvinculada." if ok else "No había ninguna cuenta vinculada.")

    async def on_error(update, ctx: ContextTypes.DEFAULT_TYPE):
        # Conflict: dos instancias hacen polling a la vez (solapamiento de un redespliegue); PTB reintenta solo.
        if isinstance(ctx.error, Conflict):
            logging.getLogger("worker").warning("Telegram Conflict: otra instancia del bot está activa (transitorio en redespliegues)")
        else:
            logging.getLogger("worker").error("Error en el bot: %s", ctx.error)

    application = Application.builder().token(token).build()
    application.add_error_handler(on_error)
    for name, fn in (("start", start), ("vincular", vincular), ("estado", estado), ("desvincular", desvincular), ("probar", probar)):
        application.add_handler(CommandHandler(name, fn))
    return application
