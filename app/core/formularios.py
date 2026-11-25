"""Formularios del núcleo (Flask-WTF: incluyen token CSRF)."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import DataRequired, Length, Regexp

# Nombres de usuario de STOD: letras, números, punto, guion y guion bajo.
PATRON_USUARIO_STOD = r"^[A-Za-z0-9._-]+$"
# Nombres de personas: letras (con tildes y ñ), espacios, guion y apóstrofo.
PATRON_NOMBRE = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]+$"


def _limpiar_espacios(valor):
    return " ".join(valor.split()) if isinstance(valor, str) else valor


def _campo_nombre(etiqueta: str) -> StringField:
    return StringField(
        etiqueta,
        filters=[_limpiar_espacios],
        validators=[
            DataRequired(message=f"Indica {etiqueta.lower()}."),
            Length(max=100),
            Regexp(PATRON_NOMBRE, message="Solo letras, espacios, guion y apóstrofo."),
        ],
    )


class FormAcceso(FlaskForm):
    usuario = StringField("Usuario STOD", validators=[DataRequired(message="Escribe tu usuario."), Length(max=100)])
    contrasena = PasswordField(
        "Contraseña", validators=[DataRequired(message="Escribe tu contraseña."), Length(max=256)],
    )


class FormPrerregistro(FlaskForm):
    usuario_stod = StringField(
        "Usuario STOD",
        validators=[DataRequired(message="Indica el usuario STOD."), Length(max=100), Regexp(PATRON_USUARIO_STOD, message="Usuario no válido.")],
    )
    # STOD no guarda el nombre: se registra aquí y es el que se muestra en el sistema.
    nombres = _campo_nombre("Nombres")
    apellidos = _campo_nombre("Apellidos")


class FormUsuario(FlaskForm):
    nombres = _campo_nombre("Nombres")
    apellidos = _campo_nombre("Apellidos")
    activo = BooleanField("Habilitado en ORBIT Canella", default=True)
