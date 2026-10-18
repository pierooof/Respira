"""Comandos `flask ...`."""
import click


def register(app):
    @app.cli.command("seed")
    def seed_cmd():
        """Carga distritos y usuario demo (idempotente)."""
        from .seed import seed
        seed()
        click.echo("Seed completado.")

    @app.cli.command("send-alerts")
    def send_alerts_cmd():
        """Envía ahora los avisos pendientes para mañana (útil para probar el bot)."""
        from worker.jobs import send_alerts
        send_alerts(app)
        click.echo("Avisos procesados.")
