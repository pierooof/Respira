"""Proceso worker (servicio aparte en Railway): `python -m worker.main`.

Planificador APScheduler en segundo plano + bot de Telegram (long polling) en el hilo principal.
Sin TELEGRAM_TOKEN solo corre el planificador.
"""
import logging
import os
import signal
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from app import create_app
from worker import bot, jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("worker")
# httpx registra la URL completa en INFO y la de Telegram lleva el token del bot: nunca debe llegar a los logs.
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def main():
    app = create_app()
    refresh_minutes = app.config["REFRESH_MINUTES"]
    alert_hour = int(os.getenv("ALERT_HOUR", "19"))

    sched = BackgroundScheduler(timezone="Europe/Madrid")
    sched.add_job(jobs.refresh, "interval", minutes=refresh_minutes, args=[app], id="refresh",
                  coalesce=True, max_instances=1, misfire_grace_time=300)
    # Aviso diario con la previsión de mañana
    sched.add_job(jobs.send_alerts, "cron", hour=alert_hour, minute=0, args=[app], id="alerts",
                  coalesce=True, max_instances=1, misfire_grace_time=1800)
    sched.start()

    # Primer arranque: poblar caché e histórico sin bloquear el bot
    def bootstrap():
        if jobs.wait_for_schema(app):
            jobs.refresh(app)
            jobs.backfill(app)
        else:
            log.error("La base de datos no tiene distritos: ¿se ejecutaron migraciones y seed en el servicio web?")

    threading.Thread(target=bootstrap, daemon=True).start()
    log.info("Planificador activo: refresco cada %s min, avisos a las %s:00", refresh_minutes, alert_hour)

    if app.config["TELEGRAM_TOKEN"]:
        bot.build(app).run_polling(drop_pending_updates=True)
    else:
        log.warning("TELEGRAM_TOKEN vacío: bot y avisos desactivados")
        signal.pause()


if __name__ == "__main__":
    main()
