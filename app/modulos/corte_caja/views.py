"""Panel del corte de caja: correos por estado, detalle y empresas.

Sin decoradores de seguridad: el núcleo exige sesión y el permiso del módulo en todas las rutas
de este Blueprint (reemplaza la autenticación básica del prototipo).
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.core.ejecuciones import EjecucionEnCurso, ejecutar_tarea
from app.core.logs import get_logger
from app.core.paginacion import POR_PAGINA, pagina_actual
from app.core.permisos import es_administrador
from app.extensions import db

from . import configuracion
from .models import Correo, Empresa

bp = Blueprint("corte_caja", __name__, template_folder="templates")
log = get_logger("corte_caja")

# (estado, título, ícono, color de Tabler): el mismo color en la pestaña, su contador y el detalle.
PESTANAS = (
    (Correo.PROCESADO, "Procesados", "circle-check", "green"),
    (Correo.RECHAZADO, "Rechazados", "mail-x", "yellow"),
    (Correo.IGNORADO, "Ignorados", "mail-off", "secondary"),
    (Correo.ERROR, "Con error", "alert-triangle", "red"),
)


def _fecha(nombre: str) -> date | None:
    try:
        return date.fromisoformat(request.args.get(nombre, ""))
    except ValueError:
        return None


def _utc(dia: date, hora: time) -> datetime:
    """Inicio o fin de un día local expresado en UTC sin zona (como se guarda ``recibido``)."""
    return datetime.combine(dia, hora).astimezone().astimezone(timezone.utc).replace(tzinfo=None)


@bp.route("/")
def inicio():
    estado = request.args.get("estado") or Correo.PROCESADO
    if estado not in Correo.ESTADOS:
        estado = Correo.PROCESADO
    filtro = {
        "empresa": request.args.get("empresa") or "",
        "texto": (request.args.get("texto") or "").strip(),
        "desde": _fecha("desde"),
        "hasta": _fecha("hasta"),
    }
    consulta = Correo.query.filter_by(estado=estado)
    if filtro["empresa"]:
        consulta = consulta.filter(Correo.empresa == filtro["empresa"])
    if filtro["texto"]:
        patron = f"%{filtro['texto'].lower()}%"
        consulta = consulta.filter(db.or_(db.func.lower(Correo.asunto).like(patron), db.func.lower(Correo.remitente).like(patron)))
    if filtro["desde"]:
        consulta = consulta.filter(Correo.recibido >= _utc(filtro["desde"], time.min))
    if filtro["hasta"]:
        consulta = consulta.filter(Correo.recibido <= _utc(filtro["hasta"], time.max))
    pagina = consulta.order_by(Correo.recibido.desc(), Correo.id.desc()).paginate(
        page=pagina_actual(), per_page=POR_PAGINA, error_out=False)

    conteos = dict(db.session.query(Correo.estado, db.func.count(Correo.id)).group_by(Correo.estado).all())
    return render_template(
        "corte_caja/inicio.html",
        correos=pagina.items, pagina=pagina, estado=estado, pestanas=PESTANAS, conteos=conteos, filtro=filtro,
        empresas=Empresa.query.order_by(Empresa.orden, Empresa.carpeta).all(),
        modo=configuracion.modo_actual(),
    )


@bp.route("/correos/<int:correo_id>")
def detalle(correo_id: int):
    correo = db.session.get(Correo, correo_id) or abort(404)
    # El enlace a la ejecución lleva a Administración: solo se muestra a quien puede abrirla.
    return render_template("corte_caja/detalle.html", correo=correo, ver_ejecucion=es_administrador())


@bp.route("/procesar", methods=["POST"])
def procesar_ahora():
    """Revisa el buzón sin esperar a la tarea programada."""
    try:
        ejecucion = ejecutar_tarea("corte_caja", "procesar", usuario_id=current_user.id)
    except EjecucionEnCurso as exc:
        flash(f"{exc} Espera a que termine.", "warning")
        return redirect(url_for("corte_caja.inicio"))
    if ejecucion.estado == "error":
        flash(f"La revisión del buzón terminó con error: {ejecucion.error}", "danger")
    elif ejecucion.estado == "sin_cambios":
        flash("No había correos nuevos en el buzón.", "info")
    elif ejecucion.estado == "advertencia":
        flash("Revisión terminada: algunos correos tuvieron error. Revisa la pestaña «Con error».", "warning")
    else:
        flash("Revisión del buzón terminada.", "success")
    return redirect(url_for("corte_caja.inicio"))
