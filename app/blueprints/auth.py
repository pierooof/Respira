from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import LoginForm, RegisterForm
from ..models import User

bp = Blueprint("auth", __name__)


def safe_next(target: str | None) -> str:
    """Solo rutas relativas del propio sitio (evita open redirect)."""
    if target:
        parts = urlsplit(target)
        if not parts.scheme and not parts.netloc and target.startswith("/") and not target.startswith("//"):
            return target
    return url_for("main.index")


@bp.route("/registro", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.email.errors.append("Ya existe una cuenta con ese correo.")
        else:
            login_user(user)
            flash("¡Bienvenido a Respira!", "success")
            return redirect(url_for("account.account"))
    return render_template("auth/register.html", form=form)


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(safe_next(request.args.get("next")))
        flash("Correo o contraseña incorrectos.", "error")  # mensaje genérico a propósito
    return render_template("auth/login.html", form=form)


@bp.post("/salir")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))
