def register_blueprints(app):
    from .health import bp as health
    app.register_blueprint(health)
