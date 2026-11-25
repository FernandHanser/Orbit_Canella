"""Administración: usuarios, permisos por módulo, catálogo, ejecuciones y logs.

El acceso exige rol de administrador (y el catálogo de módulos, superadministrador); lo
verifica ``autorizacion.controlar_acceso`` para todo el Blueprint ``admin``.
"""
from __future__ import annotations

from datetime import date

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app.core.catalogo import sincronizar_catalogo
from app.core.formularios import FormPrerregistro, FormUsuario
from app.core.identidad import IdentidadNoDisponible, normalizar_usuario, proveedor_identidad
from app.core.logs import NIVELES, buscar_logs, get_logger
from app.core.roles import ROLES_ASIGNABLES_WEB
from app.core.models import Ejecucion, Modulo, PermisoModulo, Usuario
from app.core.paginacion import POR_PAGINA, PaginaLista, pagina_actual
from app.core.peticiones import es_url_segura
from app.core.registro import registro
from app.extensions import db

bp = Blueprint("admin", __name__, url_prefix="/admin")
log = get_logger("core")

MAX_EVENTOS_LOGS = 5000  # tope de lectura de archivos por consulta
# Logs abre sin el DEBUG (arranque, registro de módulos): es ruido para quien busca qué pasó.
# Sigue disponible eligiendo «Todos» en el filtro (nivel=""), que es distinto de no mandar nivel.
NIVEL_LOGS_POR_DEFECTO = "INFO"


# --------------------------------------------------------------------------- utilidades

def _aplicar_permisos(usuario: Usuario, solicitados: set[str]) -> tuple[list[str], list[str]]:
    """Sincroniza los permisos del usuario con los módulos solicitados del catálogo."""
    validos = {m.id for m in Modulo.query.all()}
    solicitados &= validos
    actuales = usuario.modulos_ids()
    asignados = sorted(solicitados - actuales)
    retirados = sorted(actuales - solicitados)
    for modulo_id in asignados:
        usuario.permisos.append(PermisoModulo(modulo_id=modulo_id, asignado_por_id=current_user.id))
    for permiso in list(usuario.permisos):
        if permiso.modulo_id in retirados:
            usuario.permisos.remove(permiso)
    return asignados, retirados


def _registrar_cambios_permisos(usuario: Usuario, asignados: list[str], retirados: list[str]) -> None:
    for modulo_id in asignados:
        log.info("Acceso a módulo asignado", extra={"evento": "admin.permiso_asignado", "datos": {"usuario_objetivo": usuario.usuario_stod, "modulo": modulo_id}})
    for modulo_id in retirados:
        log.info("Acceso a módulo retirado", extra={"evento": "admin.permiso_retirado", "datos": {"usuario_objetivo": usuario.usuario_stod, "modulo": modulo_id}})


def _nombres_modulos() -> dict[str, str]:
    """Identificador → nombre visible, para que Ejecuciones y Logs digan «Corte de caja diario» como
    el menú y no ``corte_caja``. Incluye los módulos que ya no tienen código (quedan en el catálogo)."""
    nombres = {"core": "Hub"}
    nombres.update({m.id: m.nombre for m in Modulo.query.all()})
    nombres.update({d.id: d.nombre for d in registro().todos()})
    return nombres


# «Volver» regresa a la lista tal como se dejó (filtros y página), no a su primera página.
# Cada lista recuerda en la sesión su última dirección; el detalle la usa para su botón.
LISTAS = {"usuarios": "admin.usuarios", "ejecuciones": "admin.ejecuciones"}


def _recordar_lista(clave: str) -> None:
    session[f"lista_{clave}"] = request.full_path.rstrip("?")


def url_volver(clave: str) -> str:
    base = url_for(LISTAS[clave])
    guardada = session.get(f"lista_{clave}")
    if guardada and es_url_segura(guardada) and guardada.split("?", 1)[0] == base:
        return guardada
    return base


@bp.context_processor
def _contexto_admin():
    return {"url_volver": url_volver}


# Reglas de la jerarquía (el superadministrador solo se asigna por consola):
def puede_editar(objetivo: Usuario) -> bool:
    """Los administradores no editan al superadministrador."""
    return current_user.es_superadmin or not objetivo.es_superadmin


def puede_cambiar_estado(objetivo: Usuario) -> bool:
    """Nadie se deshabilita a sí mismo ni al superadministrador; solo el superadministrador
    deshabilita administradores."""
    if objetivo.id == current_user.id or objetivo.es_superadmin:
        return False
    return current_user.es_superadmin or objetivo.rol == Usuario.ROL_USUARIO


def puede_asignar_rol() -> bool:
    """Solo el superadministrador elige el rol al registrar; un administrador registra usuarios."""
    return current_user.es_superadmin


def puede_cambiar_rol(objetivo: Usuario) -> bool:
    """Solo el superadministrador nombra o quita administradores."""
    return current_user.es_superadmin and objetivo.id != current_user.id and not objetivo.es_superadmin


# --------------------------------------------------------------------------- usuarios

@bp.route("/usuarios")
def usuarios():
    _recordar_lista("usuarios")
    pagina = Usuario.query.order_by(Usuario.usuario_stod).paginate(page=pagina_actual(), per_page=POR_PAGINA, error_out=False)
    return render_template("admin/usuarios.html", usuarios=pagina.items, paginacion=pagina)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
def usuario_nuevo():
    """Prerregistro: permite asignar módulos a alguien antes de su primer ingreso."""
    form = FormPrerregistro()
    modulos = Modulo.query.order_by(Modulo.nombre).all()
    seleccionados = set(request.form.getlist("modulos"))
    if form.validate_on_submit():
        clave = normalizar_usuario(form.usuario_stod.data)
        identidad = None
        if Usuario.query.filter_by(usuario_stod=clave).first():
            form.usuario_stod.errors.append("Ese usuario ya está registrado en ORBIT Canella.")
        else:
            try:
                identidad = proveedor_identidad().consultar(clave)
            except IdentidadNoDisponible:
                form.usuario_stod.errors.append("No se pudo consultar STOD. Intenta de nuevo en unos minutos.")
            else:
                if identidad is None:
                    form.usuario_stod.errors.append("Ese usuario no existe en STOD.")
        if identidad is not None:
            rol = request.form.get("rol")
            if not puede_asignar_rol() or rol not in {r.clave for r in ROLES_ASIGNABLES_WEB}:
                rol = Usuario.ROL_USUARIO
            usuario = Usuario(
                usuario_stod=clave, stod_user_id=identidad.user_id, nombre=identidad.nombre_visible,
                email=identidad.email, rol=rol, activo=True,
                nombres=form.nombres.data, apellidos=form.apellidos.data,
            )
            db.session.add(usuario)
            asignados, _ = _aplicar_permisos(usuario, seleccionados)
            db.session.commit()
            log.info("Usuario prerregistrado", extra={"evento": "admin.usuario_prerregistrado", "datos": {
                "usuario_objetivo": clave, "rol": rol, "nombre": usuario.nombre_completo}})
            _registrar_cambios_permisos(usuario, asignados, [])
            if identidad.activo:
                flash(f"{usuario.nombre_completo} ({clave}) registrado.", "success")
            else:
                flash(f"{usuario.nombre_completo} ({clave}) registrado. Atención: está inactivo o bloqueado en STOD y no podrá entrar hasta que lo activen allá.", "warning")
            return redirect(url_for("admin.usuario_editar", usuario_id=usuario.id))
    return render_template(
        "admin/usuario_form.html", form=form, usuario=None, modulos=modulos, seleccionados=seleccionados, registro=registro(),
        puede_cambiar_rol=puede_asignar_rol(), rol_actual=request.form.get("rol", Usuario.ROL_USUARIO),
    )


@bp.route("/usuarios/<int:usuario_id>", methods=["GET", "POST"])
def usuario_editar(usuario_id: int):
    usuario = db.session.get(Usuario, usuario_id) or abort(404)
    if not puede_editar(usuario):
        abort(403)
    form = FormUsuario(obj=usuario)
    modulos = Modulo.query.order_by(Modulo.nombre).all()
    seleccionados = set(request.form.getlist("modulos")) if request.method == "POST" else usuario.modulos_ids()

    if form.validate_on_submit():
        cambios = {}
        if (form.nombres.data, form.apellidos.data) != (usuario.nombres, usuario.apellidos):
            usuario.nombres, usuario.apellidos = form.nombres.data, form.apellidos.data
            cambios["nombre"] = usuario.nombre_completo
        if puede_cambiar_estado(usuario) and usuario.activo != form.activo.data:
            usuario.activo = form.activo.data
            cambios["activo"] = usuario.activo
        rol = request.form.get("rol")
        if puede_cambiar_rol(usuario) and rol in {r.clave for r in ROLES_ASIGNABLES_WEB} and rol != usuario.rol:
            usuario.rol = rol
            cambios["rol"] = rol
        if cambios.get("activo") is False or "rol" in cambios:
            usuario.invalidar_sesiones()
        asignados, retirados = _aplicar_permisos(usuario, seleccionados)
        db.session.commit()
        if cambios:
            log.info("Usuario actualizado", extra={"evento": "admin.usuario_actualizado", "datos": {"usuario_objetivo": usuario.usuario_stod, "cambios": cambios}})
        _registrar_cambios_permisos(usuario, asignados, retirados)
        flash("Cambios guardados.", "success")
        return redirect(url_for("admin.usuario_editar", usuario_id=usuario.id))

    return render_template(
        "admin/usuario_form.html", form=form, usuario=usuario, modulos=modulos, seleccionados=seleccionados, registro=registro(),
        puede_cambiar_estado=puede_cambiar_estado(usuario), puede_cambiar_rol=puede_cambiar_rol(usuario), rol_actual=usuario.rol,
    )


# --------------------------------------------------------------------------- módulos

@bp.route("/modulos")
def modulos():
    catalogo = {m.id: m for m in Modulo.query.all()}
    registrados = {d.id: d for d in registro().todos()}
    ids = sorted(set(catalogo) | set(registrados), key=lambda i: (catalogo.get(i) or registrados.get(i)).nombre.lower())
    usuarios_por_modulo = dict(
        db.session.query(PermisoModulo.modulo_id, db.func.count(PermisoModulo.usuario_id)).group_by(PermisoModulo.modulo_id).all()
    )
    filas = [
        {"id": i, "catalogo": catalogo.get(i), "definicion": registrados.get(i), "usuarios": usuarios_por_modulo.get(i, 0)}
        for i in ids
    ]
    return render_template("admin/modulos.html", filas=filas)


@bp.route("/modulos/sincronizar", methods=["POST"])
def modulos_sincronizar():
    resultado = sincronizar_catalogo()
    flash(f"Catálogo sincronizado. Nuevos: {len(resultado['creados'])}; actualizados: {len(resultado['actualizados'])}.", "success")
    return redirect(url_for("admin.modulos"))


@bp.route("/modulos/<modulo_id>/estado", methods=["POST"])
def modulo_estado(modulo_id: str):
    modulo = db.session.get(Modulo, modulo_id) or abort(404)
    modulo.activo = request.form.get("activo") == "1"
    db.session.commit()
    evento = "admin.modulo_habilitado" if modulo.activo else "admin.modulo_deshabilitado"
    log.info("Estado de módulo actualizado", extra={"evento": evento, "datos": {"modulo": modulo.id}})
    flash(f"Módulo «{modulo.nombre}» {'habilitado' if modulo.activo else 'deshabilitado'}.", "success")
    return redirect(url_for("admin.modulos"))


# --------------------------------------------------------------------------- ejecuciones y logs

@bp.route("/ejecuciones")
def ejecuciones():
    _recordar_lista("ejecuciones")
    modulo = request.args.get("modulo") or None
    estado = request.args.get("estado") or None
    consulta = Ejecucion.query
    if modulo:
        consulta = consulta.filter_by(modulo_id=modulo)
    if estado is None:
        # Por defecto se ocultan las corridas sin nada que procesar; "todas" las incluye.
        consulta = consulta.filter(Ejecucion.estado != "sin_cambios")
    elif estado != "todas":
        consulta = consulta.filter_by(estado=estado)
    pagina = consulta.order_by(Ejecucion.inicio.desc()).paginate(page=pagina_actual(), per_page=POR_PAGINA, error_out=False)
    return render_template(
        "admin/ejecuciones.html", ejecuciones=pagina.items, paginacion=pagina, modulos=Modulo.query.order_by(Modulo.nombre).all(),
        estados=Ejecucion.ESTADOS, filtro={"modulo": modulo, "estado": estado}, nombres_modulos=_nombres_modulos(),
    )


@bp.route("/ejecuciones/<ejecucion_id>")
def ejecucion_detalle(ejecucion_id: str):
    ejecucion = db.session.get(Ejecucion, ejecucion_id)
    if ejecucion is None:
        # Las ejecuciones «sin cambios» antiguas se purgan; sus eventos pueden seguir en los logs.
        flash("Esa ejecución ya no está registrada; se muestran los eventos que quedan de ella.", "info")
        return redirect(url_for("admin.logs", ejecucion_id=ejecucion_id, nivel="", dias=current_app.config["LOG_RETENCION_DIAS"]))
    # Se buscan los logs desde el día en que empezó (hasta donde alcance la retención), no solo el último mes.
    retencion = current_app.config["LOG_RETENCION_DIAS"]
    dias = min((date.today() - ejecucion.inicio.date()).days + 2, retencion)
    eventos = buscar_logs(current_app.config["LOG_DIR"], ejecucion_id=ejecucion.id, dias=dias, limite=1000)
    return render_template("admin/ejecucion_detalle.html", ejecucion=ejecucion, eventos=list(reversed(eventos)),
                           nombres_modulos=_nombres_modulos())


@bp.route("/logs")
def logs():
    filtro = {
        "modulo": request.args.get("modulo") or None,
        "ejecucion_id": (request.args.get("ejecucion_id") or "").strip() or None,
        "nivel_minimo": request.args.get("nivel", NIVEL_LOGS_POR_DEFECTO) or None,
        "usuario": (request.args.get("usuario") or "").strip() or None,
        "texto": (request.args.get("texto") or "").strip() or None,
        "dias": request.args.get("dias", default=1, type=int),
    }
    filtro["dias"] = min(max(filtro["dias"], 1), current_app.config["LOG_RETENCION_DIAS"])
    eventos = buscar_logs(current_app.config["LOG_DIR"], limite=MAX_EVENTOS_LOGS, **filtro)
    pagina = PaginaLista(eventos, pagina_actual(), POR_PAGINA)
    nombres = _nombres_modulos()
    # El hub primero; después los módulos por nombre, como en el menú.
    modulos_ids = ["core"] + sorted((i for i in nombres if i != "core"), key=lambda i: nombres[i].lower())
    return render_template("admin/logs.html", eventos=pagina.items, paginacion=pagina, tope=MAX_EVENTOS_LOGS, filtro=filtro,
                           niveles=NIVELES, modulos_ids=modulos_ids, nombres_modulos=nombres)
