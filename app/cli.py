"""Comandos `flask ...`."""
import click


def register(app):
    @app.cli.command("seed")
    def seed_cmd():
        """Carga distritos y usuario demo (idempotente)."""
        from .seed import seed
        seed()
        click.echo("Seed completado.")
