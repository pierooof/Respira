from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterForm(FlaskForm):
    email = StringField("Correo electrónico", filters=[lambda s: (s or "").strip().lower()], validators=[
        DataRequired("Escribe tu correo."), Length(max=190), Regexp(EMAIL_RE, message="Correo no válido.")])
    password = PasswordField("Contraseña", validators=[
        DataRequired("Escribe una contraseña."), Length(min=8, max=128, message="Entre 8 y 128 caracteres.")])
    confirm = PasswordField("Repite la contraseña", validators=[
        EqualTo("password", message="Las contraseñas no coinciden.")])


class LoginForm(FlaskForm):
    email = StringField("Correo electrónico", filters=[lambda s: (s or "").strip().lower()],
                        validators=[DataRequired(), Length(max=190)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(max=128)])
