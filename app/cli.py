"""Comandos `flask ...`."""
import click


def register(app):
    @app.cli.command("seed")
    def seed_cmd():
        """Carga distritos y usuario demo (idempotente)."""
        from .seed import seed
        seed()
        click.echo("Seed completado.")

    @app.cli.command("remove-demo")
    def remove_demo_cmd():
        """Elimina la cuenta demo. Con SEED_DEMO_USER=false no se vuelve a crear en el arranque."""
        from .seed import remove_demo
        click.echo("Cuenta demo eliminada." if remove_demo() else "La cuenta demo no existía.")

    @app.cli.command("send-alerts")
    def send_alerts_cmd():
        """Envía ahora los avisos pendientes para mañana (útil para probar el bot)."""
        from worker.jobs import send_alerts
        send_alerts(app)
        click.echo("Avisos procesados.")

    @app.cli.command("simulate-alert")
    @click.option("--email", default=None, help="Usuario destino (por defecto, el primero con Telegram vinculado)")
    def simulate_alert_cmd(email):
        """Envía un aviso de polen simulado «para mañana» (prueba puntual de entrega por Telegram)."""
        from worker.jobs import simulate_alert
        click.echo(simulate_alert(app, email))
