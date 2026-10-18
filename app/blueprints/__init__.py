def register_blueprints(app):
    from .account import bp as account
    from .auth import bp as auth
    from .health import bp as health
    from .main import bp as main

    for bp in (health, main, auth, account):
        app.register_blueprint(bp)
