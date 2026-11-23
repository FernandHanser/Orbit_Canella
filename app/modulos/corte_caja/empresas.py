"""Administración de empresas desde el panel.

Todos los usuarios del módulo ven la lista; crear, editar, activar o desactivar y eliminar es
solo para administradores del hub (``app.core.permisos``). Las mismas operaciones existen por
consola en ``cli.py``.
"""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, url_for
from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp, ValidationError

from app.core.logs import get_logger
from app.core.permisos import es_administrador, solo_administradores
from app.extensions import db

from . import reglas
from .models import Correo, Empresa
from .views import bp

log = get_logger("corte_caja")


def limpiar_claves(texto: str) -> str:
    """Palabras clave separadas por coma, sin vacías ni repetidas (comparadas sin tildes ni mayúsculas)."""
    vistas, claves = set(), []
    for clave in (texto or "").split(","):
        clave = " ".join(clave.split()).lower()
        if clave and reglas.normalizar(clave) and reglas.normalizar(clave) not in vistas:
            vistas.add(reglas.normalizar(clave))
            claves.append(clave)
    return ",".join(claves)


class FormEmpresa(FlaskForm):
    carpeta = StringField(
        "Carpeta de destino",
        validators=[
            DataRequired(message="Indica el nombre de la carpeta."),
            Length(max=100),
            Regexp(r'^[^\\/:*?"<>|]+$', message='Sin los caracteres \\ / : * ? " < > |'),
        ],
    )
    palabras_clave = StringField(
        "Palabras clave",
        validators=[DataRequired(message="Indica al menos una palabra clave."), Length(max=500)],
    )
    orden = IntegerField("Orden", default=100, validators=[DataRequired(message="Indica el orden."), NumberRange(min=1, max=9999)])
    activa = BooleanField("Activa", default=True)

    def __init__(self, *args, empresa_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._empresa_id = empresa_id

    def validate_carpeta(self, campo):
        valor = campo.data.strip()
        if valor.endswith(".") or valor != campo.data:
            raise ValidationError("No puede empezar ni terminar con espacios, ni terminar en punto.")
        existente = Empresa.query.filter(db.func.lower(Empresa.carpeta) == valor.lower()).first()
        if existente is not None and existente.id != self._empresa_id:
            raise ValidationError("Ya existe una empresa con esa carpeta.")

    def validate_palabras_clave(self, campo):
        if not limpiar_claves(campo.data):
            raise ValidationError("Indica al menos una palabra clave con letras o números.")


def _datos(empresa: Empresa) -> dict:
    return {"carpeta": empresa.carpeta, "palabras_clave": empresa.palabras_clave, "orden": empresa.orden, "activa": empresa.activa}


@bp.route("/empresas")
def empresas():
    return render_template(
        "corte_caja/empresas.html",
        empresas=Empresa.query.order_by(Empresa.orden, Empresa.carpeta).all(),
        puede_editar=es_administrador(),
    )


@bp.route("/empresas/nueva", methods=["GET", "POST"])
@solo_administradores
def empresa_nueva():
    form = FormEmpresa()
    if form.validate_on_submit():
        empresa = Empresa(carpeta=form.carpeta.data, palabras_clave=limpiar_claves(form.palabras_clave.data),
                          orden=form.orden.data, activa=form.activa.data)
        db.session.add(empresa)
        db.session.commit()
        log.info("Empresa agregada", extra={"evento": "corte_caja.empresa_agregada", "datos": _datos(empresa)})
        flash(f"Empresa «{empresa.carpeta}» agregada.", "success")
        return redirect(url_for("corte_caja.empresas"))
    return render_template("corte_caja/empresa_form.html", form=form, empresa=None)


@bp.route("/empresas/<int:empresa_id>", methods=["GET", "POST"])
@solo_administradores
def empresa_editar(empresa_id: int):
    empresa = db.session.get(Empresa, empresa_id) or abort(404)
    form = FormEmpresa(obj=empresa, empresa_id=empresa.id)
    if form.validate_on_submit():
        antes = _datos(empresa)
        empresa.carpeta = form.carpeta.data
        empresa.palabras_clave = limpiar_claves(form.palabras_clave.data)
        empresa.orden = form.orden.data
        empresa.activa = form.activa.data
        db.session.commit()
        log.info("Empresa modificada", extra={"evento": "corte_caja.empresa_modificada",
                                              "datos": {"antes": antes, "despues": _datos(empresa)}})
        flash(f"Empresa «{empresa.carpeta}» actualizada.", "success")
        return redirect(url_for("corte_caja.empresas"))
    return render_template("corte_caja/empresa_form.html", form=form, empresa=empresa)


@bp.route("/empresas/<int:empresa_id>/eliminar", methods=["POST"])
@solo_administradores
def empresa_eliminar(empresa_id: int):
    """Solo si ningún correo la usa: el historial guarda el nombre de la empresa. Si ya tiene
    correos, se desactiva en lugar de eliminarla."""
    empresa = db.session.get(Empresa, empresa_id) or abort(404)
    usados = Correo.query.filter_by(empresa=empresa.carpeta).count()
    if usados:
        flash(f"«{empresa.carpeta}» tiene {usados} correo(s) en el historial: desactívala en lugar de eliminarla.", "warning")
        return redirect(url_for("corte_caja.empresas"))
    datos = _datos(empresa)
    db.session.delete(empresa)
    db.session.commit()
    log.info("Empresa eliminada", extra={"evento": "corte_caja.empresa_eliminada", "datos": datos})
    flash(f"Empresa «{datos['carpeta']}» eliminada.", "success")
    return redirect(url_for("corte_caja.empresas"))
