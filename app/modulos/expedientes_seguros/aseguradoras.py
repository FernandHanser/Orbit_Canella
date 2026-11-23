"""Configuración del correo por aseguradora (solo administradores del hub).

Todos los usuarios del módulo ven la lista; crear, editar y eliminar aseguradoras y cambiar el
correo por defecto o el modo de envío (prueba/producción) es solo para administradores
(``app.core.permisos``).
"""
from __future__ import annotations

import re

from flask import abort, flash, redirect, render_template, request, url_for
from flask_wtf import FlaskForm
from sqlalchemy.orm import selectinload
from wtforms import BooleanField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.core.logs import get_logger
from app.core.permisos import es_administrador, solo_administradores
from app.extensions import db

from . import reglas, servicios
from .models import Aseguradora, CodigoAseguradora, Documento, Paquete, Parametro
from .views import bp

log = get_logger("expedientes_seguros")
_CODIGO = re.compile(r"^[A-Za-z0-9-]{1,20}$")
def _codigos(texto: str) -> list[str]:
    return sorted({c.strip().upper() for c in re.split(r"[,;\s]+", texto or "") if c.strip()})


def _validar_correos(campo):
    invalido = reglas.correo_invalido(campo.data)
    if invalido:
        raise ValidationError(f"La dirección «{invalido}» no es válida.")


class FormAseguradora(FlaskForm):
    nombre = StringField("Nombre corto", validators=[DataRequired(message="Indica el nombre."), Length(max=150)])
    codigos = StringField("Códigos de socio en SAP", validators=[DataRequired(message="Indica al menos un código.")])
    para = TextAreaField("Para", validators=[Optional(), Length(max=1000)])
    cc = TextAreaField("CC", validators=[Optional(), Length(max=1000)])
    asunto = StringField("Asunto", validators=[Optional(), Length(max=300)])
    cuerpo = TextAreaField("Cuerpo", validators=[Optional()])
    activa = BooleanField("Activa", default=True)

    def __init__(self, *args, aseguradora_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._id = aseguradora_id

    def validate_nombre(self, campo):
        otra = Aseguradora.query.filter(db.func.lower(Aseguradora.nombre) == campo.data.strip().lower()).first()
        if otra and otra.id != self._id:
            raise ValidationError("Ya existe una aseguradora con ese nombre.")

    def validate_codigos(self, campo):
        for codigo in _codigos(campo.data):
            if not _CODIGO.match(codigo):
                raise ValidationError(f"«{codigo}» no es un código válido (ej. C000078).")
            fila = db.session.get(CodigoAseguradora, codigo)
            if fila and fila.aseguradora_id != self._id:
                raise ValidationError(f"El código {codigo} ya es de {fila.aseguradora.nombre}.")

    def validate_para(self, campo):
        _validar_correos(campo)

    def validate_cc(self, campo):
        _validar_correos(campo)


class FormParametros(FlaskForm):
    para = TextAreaField("Para", validators=[DataRequired(message="Indica al menos un destinatario."), Length(max=1000)])
    cc = TextAreaField("CC", validators=[Optional(), Length(max=1000)])
    asunto = StringField("Asunto", validators=[DataRequired(message="Indica el asunto."), Length(max=300)])
    cuerpo = TextAreaField("Cuerpo", validators=[DataRequired(message="Indica el cuerpo.")])

    def validate_para(self, campo):
        _validar_correos(campo)

    def validate_cc(self, campo):
        _validar_correos(campo)


def _guardar(aseguradora: Aseguradora, form: FormAseguradora) -> None:
    aseguradora.nombre = form.nombre.data.strip()
    aseguradora.activa = form.activa.data
    for campo in ("para", "cc", "asunto", "cuerpo"):
        setattr(aseguradora, campo, (getattr(form, campo).data or "").strip() or None)
    nuevos = _codigos(form.codigos.data)
    aseguradora.codigos = [c for c in aseguradora.codigos if c.codigo in nuevos]
    actuales = {c.codigo for c in aseguradora.codigos}
    aseguradora.codigos += [CodigoAseguradora(codigo=c) for c in nuevos if c not in actuales]


@bp.route("/aseguradoras")
def aseguradoras():
    # selectinload: la plantilla lee "codigos" y "documentos" de cada fila (lista_codigos, cuántos
    # documentos y cuántos inactivos). Sin esto, cada fila dispara sus propias consultas (N+1).
    lista = Aseguradora.query.options(
        selectinload(Aseguradora.codigos), selectinload(Aseguradora.documentos),
    ).order_by(Aseguradora.nombre).all()
    return render_template(
        "expedientes_seguros/aseguradoras.html",
        aseguradoras=lista, parametros=servicios.parametros(), puede_editar=es_administrador(),
    )


@bp.route("/aseguradoras/nueva", methods=["GET", "POST"])
@solo_administradores
def aseguradora_nueva():
    form = FormAseguradora()
    if form.validate_on_submit():
        aseguradora = Aseguradora()
        _guardar(aseguradora, form)
        db.session.add(aseguradora)
        db.session.commit()
        log.info("Aseguradora agregada", extra={"evento": "expedientes.aseguradora_agregada",
                                                "datos": {"nombre": aseguradora.nombre, "codigos": aseguradora.lista_codigos}})
        flash(f"Aseguradora «{aseguradora.nombre}» agregada.", "success")
        return redirect(url_for("expedientes_seguros.aseguradoras"))
    return render_template("expedientes_seguros/aseguradora_form.html", form=form, aseguradora=None,
                           parametros=servicios.parametros())


@bp.route("/aseguradoras/<int:aseguradora_id>", methods=["GET", "POST"])
@solo_administradores
def aseguradora_editar(aseguradora_id: int):
    aseguradora = db.session.get(Aseguradora, aseguradora_id) or abort(404)
    form = FormAseguradora(obj=aseguradora, aseguradora_id=aseguradora.id)
    if not form.is_submitted():
        form.codigos.data = aseguradora.lista_codigos

    if form.validate_on_submit():
        _guardar(aseguradora, form)
        db.session.commit()
        log.info("Aseguradora modificada", extra={"evento": "expedientes.aseguradora_modificada",
                                                  "datos": {"nombre": aseguradora.nombre, "codigos": aseguradora.lista_codigos}})
        flash(f"Aseguradora «{aseguradora.nombre}» actualizada.", "success")
        return redirect(url_for("expedientes_seguros.aseguradoras"))
    return render_template("expedientes_seguros/aseguradora_form.html", form=form, aseguradora=aseguradora,
                           parametros=servicios.parametros())


@bp.route("/aseguradoras/<int:aseguradora_id>/eliminar", methods=["POST"])
@solo_administradores
def aseguradora_eliminar(aseguradora_id: int):
    aseguradora = db.session.get(Aseguradora, aseguradora_id) or abort(404)
    codigos = [c.codigo for c in aseguradora.codigos]
    usados = Paquete.query.filter(Paquete.aseguradora_codigo.in_(codigos)).count() if codigos else 0
    if usados:
        flash(f"«{aseguradora.nombre}» tiene {usados} paquete(s) registrados: desactívala en lugar de eliminarla.", "warning")
        return redirect(url_for("expedientes_seguros.aseguradoras"))
    nombre = aseguradora.nombre
    db.session.delete(aseguradora)
    db.session.commit()
    log.info("Aseguradora eliminada", extra={"evento": "expedientes.aseguradora_eliminada", "datos": {"nombre": nombre}})
    flash(f"Aseguradora «{nombre}» eliminada.", "success")
    return redirect(url_for("expedientes_seguros.aseguradoras"))


# ------------------------------------------------------------------ checklist

def _filas_del_formulario(formulario) -> list[dict]:
    """Filas del editor en el orden de la pantalla. Cada fila tiene una clave: el id del documento
    o ``n<número>`` si es nueva."""
    filas = []
    for clave in formulario.getlist("orden"):
        filas.append({
            "clave": clave,
            "nombre": " ".join((formulario.get(f"nombre-{clave}") or "").split())[:200],
            "obligatorio": formulario.get(f"obligatorio-{clave}") == "1",
            "activo": formulario.get(f"activo-{clave}") == "1",
            "separado": formulario.get(f"separado-{clave}") == "1",
            "quitar": formulario.get(f"quitar-{clave}") == "1",
        })
    return filas


def _errores_checklist(filas: list[dict]) -> list[str]:
    errores, vistos = [], set()
    for posicion, fila in enumerate(filas, start=1):
        if fila["quitar"]:
            continue
        if not fila["nombre"]:
            errores.append(f"La fila {posicion} no tiene nombre (escríbelo o márcala para quitar).")
            continue
        clave = fila["nombre"].lower()
        if clave in vistos:
            errores.append(f"«{fila['nombre']}» está repetido.")
        vistos.add(clave)
    return errores


@bp.route("/aseguradoras/<int:aseguradora_id>/checklist", methods=["GET", "POST"])
@solo_administradores
def checklist(aseguradora_id: int):
    aseguradora = db.session.get(Aseguradora, aseguradora_id) or abort(404)
    if request.method == "POST":
        filas = _filas_del_formulario(request.form)
        errores = _errores_checklist(filas)
        if errores:
            return render_template("expedientes_seguros/checklist.html", aseguradora=aseguradora, filas=filas,
                                   errores=errores), 422
        existentes = {str(d.id): d for d in aseguradora.documentos}
        conservados, orden = [], 0
        for fila in filas:
            if fila["quitar"]:
                continue
            orden += 1
            documento = existentes.get(fila["clave"]) or Documento()
            documento.orden, documento.nombre = orden, fila["nombre"]
            documento.obligatorio, documento.activo = fila["obligatorio"], fila["activo"]
            documento.separado = fila["separado"]
            conservados.append(documento)
        quitados = [d.nombre for d in aseguradora.documentos if d not in conservados]
        aseguradora.documentos = conservados   # delete-orphan borra los quitados
        db.session.commit()
        log.info("Checklist actualizado", extra={"evento": "expedientes.checklist", "datos": {
            "aseguradora": aseguradora.nombre, "documentos": len(conservados),
            "inactivos": sum(1 for d in conservados if not d.activo), "quitados": quitados}})
        flash(f"Checklist de «{aseguradora.nombre}» guardado: {len(conservados)} documentos.", "success")
        return redirect(url_for("expedientes_seguros.checklist", aseguradora_id=aseguradora.id))
    filas = [{"clave": str(d.id), "nombre": d.nombre, "obligatorio": d.obligatorio, "activo": d.activo,
              "separado": d.separado, "quitar": False} for d in aseguradora.documentos]
    return render_template("expedientes_seguros/checklist.html", aseguradora=aseguradora, filas=filas, errores=[])


@bp.route("/modo-envio", methods=["POST"])
@solo_administradores
def modo_envio():
    modo = request.form.get("modo")
    destino = " ".join((request.form.get("destino_prueba") or "").split())
    volver = redirect(url_for("expedientes_seguros.aseguradoras"))
    if modo not in (servicios.MODO_PRUEBA, servicios.MODO_PRODUCCION):
        abort(400)
    destino = destino or servicios.modo_envio().destino_prueba
    if len(reglas.direcciones(destino)) != 1 or reglas.correo_invalido(destino):
        flash(f"El destino de prueba «{destino}» debe ser un solo correo válido.", "danger")
        return volver
    servicios.guardar_modo_envio(modo, destino)
    log.info("Modo de envío cambiado", extra={"evento": "expedientes.modo_envio", "datos": {"modo": modo, "destino_prueba": destino}})
    if modo == servicios.MODO_PRODUCCION:
        flash("Modo PRODUCCIÓN: los correos van a los destinatarios reales (Cobros).", "success")
    else:
        flash(f"Modo PRUEBA: todos los correos van solo a {destino}.", "warning")
    return volver


@bp.route("/correo-por-defecto", methods=["GET", "POST"])
@solo_administradores
def parametros():
    form = FormParametros(data=servicios.parametros())
    if form.validate_on_submit():
        for clave in servicios.PARAMETROS:
            fila = db.session.get(Parametro, clave) or Parametro(clave=clave)
            fila.valor = (getattr(form, clave).data or "").strip()
            db.session.add(fila)
        db.session.commit()
        log.info("Correo por defecto actualizado", extra={"evento": "expedientes.parametros"})
        flash("Correo por defecto actualizado.", "success")
        return redirect(url_for("expedientes_seguros.aseguradoras"))
    return render_template("expedientes_seguros/parametros_form.html", form=form)
