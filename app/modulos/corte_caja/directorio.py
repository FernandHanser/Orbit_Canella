"""Configuración del módulo: directorio de cajas y tiendas.

Traslado de la pestaña «Directorio Tiendas» del prototipo (``tiendas_api.py`` + ``index.html``):
lo ven y lo editan todos los usuarios del módulo, como allá. Cada cambio queda en el log con los
valores antes y después. Las empresas (carpeta y subcarpetas de destino) ya no tienen pantalla:
se administran por consola (``cli.py``).
"""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.core.logs import get_logger
from app.core.paginacion import POR_PAGINA, pagina_actual
from app.extensions import db

from . import cuadre
from .models import Caja
from .views import bp

log = get_logger("corte_caja")


class FormCaja(FlaskForm):
    categoria = StringField("Categoría", validators=[DataRequired(message="Indica la categoría."), Length(max=100)])
    nombre_caja = StringField("Nombre de la caja", validators=[DataRequired(message="Indica el nombre de la caja."), Length(max=150)])
    responsable = StringField("Responsable", validators=[Optional(), Length(max=150)])
    correo = StringField("Correo electrónico", validators=[Optional(), Length(max=500)])

    def validate_correo(self, campo):
        texto = (campo.data or "").strip()
        if texto and not cuadre.correos(texto):
            raise ValidationError("Escribe al menos una dirección de correo (separa varias con coma).")


def _datos(caja: Caja) -> dict:
    return {"categoria": caja.categoria, "nombre_caja": caja.nombre_caja, "responsable": caja.responsable, "correo": caja.correo}


def _llenar(caja: Caja, form: FormCaja) -> None:
    caja.categoria = " ".join(form.categoria.data.split()).upper()
    caja.nombre_caja = " ".join(form.nombre_caja.data.split())
    caja.responsable = (form.responsable.data or "").strip() or None
    caja.correo = (form.correo.data or "").strip() or None


@bp.route("/cajas")
def cajas():
    texto = (request.args.get("texto") or "").strip()
    consulta = Caja.query
    if texto:
        patron = f"%{texto.lower()}%"
        consulta = consulta.filter(db.or_(db.func.lower(Caja.categoria).like(patron), db.func.lower(Caja.nombre_caja).like(patron),
                                          db.func.lower(Caja.responsable).like(patron), db.func.lower(Caja.correo).like(patron)))
    pagina = consulta.order_by(Caja.categoria, Caja.nombre_caja, Caja.id).paginate(
        page=pagina_actual(), per_page=POR_PAGINA, error_out=False)
    return render_template("corte_caja/cajas.html", cajas=pagina.items, pagina=pagina, texto=texto)


@bp.route("/cajas/nueva", methods=["GET", "POST"])
def caja_nueva():
    form = FormCaja()
    if form.validate_on_submit():
        caja = Caja()
        _llenar(caja, form)
        db.session.add(caja)
        db.session.commit()
        log.info("Caja agregada al directorio", extra={"evento": "corte_caja.caja_agregada", "datos": _datos(caja)})
        flash(f"Caja «{caja.nombre_caja}» agregada.", "success")
        return redirect(url_for("corte_caja.cajas"))
    return render_template("corte_caja/caja_form.html", form=form, caja=None)


@bp.route("/cajas/<int:caja_id>", methods=["GET", "POST"])
def caja_editar(caja_id: int):
    caja = db.session.get(Caja, caja_id) or abort(404)
    form = FormCaja(obj=caja)
    if form.validate_on_submit():
        antes = _datos(caja)
        _llenar(caja, form)
        db.session.commit()
        log.info("Caja modificada en el directorio", extra={"evento": "corte_caja.caja_modificada",
                                                           "datos": {"antes": antes, "despues": _datos(caja)}})
        flash(f"Caja «{caja.nombre_caja}» actualizada.", "success")
        return redirect(url_for("corte_caja.cajas"))
    return render_template("corte_caja/caja_form.html", form=form, caja=caja)


@bp.route("/cajas/<int:caja_id>/eliminar", methods=["POST"])
def caja_eliminar(caja_id: int):
    caja = db.session.get(Caja, caja_id) or abort(404)
    datos = _datos(caja)
    db.session.delete(caja)
    db.session.commit()
    log.info("Caja eliminada del directorio", extra={"evento": "corte_caja.caja_eliminada", "datos": datos})
    flash(f"Caja «{datos['nombre_caja']}» eliminada.", "success")
    return redirect(url_for("corte_caja.cajas"))
