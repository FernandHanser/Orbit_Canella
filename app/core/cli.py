"""Comandos de administración (``flask --app wsgi <grupo> <comando>``)."""
from __future__ import annotations

import json
import sys

import click
from flask import Flask, current_app
from flask.cli import AppGroup

from app.core.catalogo import sincronizar_catalogo
from app.core.ejecuciones import (
    EjecucionEnCurso,
    ModuloDeshabilitado,
    TareaNoEncontrada,
    ejecutar_tarea,
    marcar_interrumpidas,
    purgar_sin_cambios,
)
from app.core.identidad import normalizar_usuario
from app.core.logs import buscar_logs, get_logger
from app.core.models import Usuario
from app.core.registro import registro
from app.extensions import db

log = get_logger("core")

usuarios_cli = AppGroup("usuarios", help="Gestión de usuarios.")
modulos_cli = AppGroup("modulos", help="Catálogo de módulos.")
tareas_cli = AppGroup("tareas", help="Tareas de módulos ejecutables sin sesión web.")
logs_cli = AppGroup("logs", help="Consulta del log central.")


@usuarios_cli.command("superadmin")
@click.argument("usuario_stod")
def superadmin(usuario_stod: str) -> None:
    """Asigna el rol de superadministrador a un usuario de STOD.

    No pide contraseña: la persona entra con su contraseña de STOD. Si todavía no ha
    ingresado al hub, queda prerregistrada y sus datos se completan en su primer ingreso.
    """
    clave = normalizar_usuario(usuario_stod)
    if not clave:
        raise click.ClickException("Indica el usuario de STOD.")
    usuario = Usuario.query.filter_by(usuario_stod=clave).first()
    if usuario is None:
        usuario = Usuario(usuario_stod=clave, nombre=clave.upper(), activo=True)
        db.session.add(usuario)
    usuario.rol = Usuario.ROL_SUPERADMIN
    usuario.activo = True
    usuario.invalidar_sesiones()
    db.session.commit()
    log.info("Superadministrador asignado desde CLI", extra={"evento": "cli.superadmin", "usuario": "proceso:cli", "datos": {"usuario_objetivo": clave}})
    click.echo(f"{clave} es superadministrador. Entra con su usuario y contraseña de STOD.")


@usuarios_cli.command("quitar-superadmin")
@click.argument("usuario_stod")
def quitar_superadmin(usuario_stod: str) -> None:
    """Devuelve a un superadministrador al rol de administrador."""
    usuario = Usuario.query.filter_by(usuario_stod=normalizar_usuario(usuario_stod)).first()
    if usuario is None or not usuario.es_superadmin:
        raise click.ClickException("Ese usuario no es superadministrador.")
    if Usuario.query.filter_by(rol=Usuario.ROL_SUPERADMIN, activo=True).count() <= 1:
        raise click.ClickException("Debe quedar al menos un superadministrador.")
    usuario.rol = Usuario.ROL_ADMIN
    usuario.invalidar_sesiones()
    db.session.commit()
    log.info("Superadministrador retirado desde CLI", extra={"evento": "cli.superadmin_retirado", "usuario": "proceso:cli", "datos": {"usuario_objetivo": usuario.usuario_stod}})
    click.echo(f"{usuario.usuario_stod} ahora es administrador.")


@usuarios_cli.command("listar")
def listar_usuarios() -> None:
    for u in Usuario.query.order_by(Usuario.usuario_stod):
        estado = "habilitado" if u.activo else "deshabilitado"
        ingreso = "sin ingresar" if u.pendiente_primer_ingreso else "ha ingresado"
        click.echo(f"{u.id:>4}  {u.usuario_stod:<20} {u.nombre_completo[:30]:<30} {u.rol:<11} {estado:<14} {ingreso:<13} módulos: {', '.join(sorted(u.modulos_ids())) or '-'}")


@modulos_cli.command("sincronizar")
def modulos_sincronizar() -> None:
    """Crea/actualiza en la base de datos los módulos registrados en código."""
    resultado = sincronizar_catalogo()
    click.echo(f"Nuevos: {resultado['creados'] or '-'}  Actualizados: {resultado['actualizados'] or '-'}")


@modulos_cli.command("listar")
def modulos_listar() -> None:
    for d in registro().todos():
        click.echo(f"{d.id:<24} {d.ruta:<28} permiso={d.permiso:<28} tareas={', '.join(d.tareas) or '-'}")


@tareas_cli.command("listar")
def tareas_listar() -> None:
    for d in registro().todos():
        for nombre in d.tareas:
            click.echo(f"{d.id} {nombre}")


SALIDA_EN_CURSO = 3
SALIDA_DESHABILITADO = 4


@tareas_cli.command("ejecutar")
@click.argument("modulo_id")
@click.argument("tarea")
@click.option("--proceso", default="cli", show_default=True, help="Nombre del proceso que inicia la ejecución (p. ej. el nombre de la tarea programada).")
@click.option("--param", "parametros", multiple=True, help="Parámetro clave=valor (repetible).")
def tareas_ejecutar(modulo_id: str, tarea: str, proceso: str, parametros: tuple[str, ...]) -> None:
    """Ejecuta una tarea sin sesión web.

    Código de salida: 0 bien, 1 si termina con error, 3 si se omitió porque el módulo ya tenía
    una ejecución en curso, 4 si se omitió porque el módulo está deshabilitado en el catálogo."""
    params = {}
    for p in parametros:
        clave, _, valor = p.partition("=")
        params[clave.strip()] = valor
    try:
        ejecucion = ejecutar_tarea(modulo_id, tarea, proceso=proceso, parametros=params)
    except TareaNoEncontrada:
        raise click.ClickException(f"No existe la tarea {tarea!r} en el módulo {modulo_id!r}.")
    except EjecucionEnCurso as exc:
        click.echo(f"Omitida: {exc}", err=True)
        sys.exit(SALIDA_EN_CURSO)
    except ModuloDeshabilitado as exc:
        click.echo(f"Omitida: {exc}", err=True)
        sys.exit(SALIDA_DESHABILITADO)
    click.echo(f"Ejecución {ejecucion.id}: {ejecucion.estado}")
    if ejecucion.resultado:
        click.echo(f"Resultado: {ejecucion.resultado}")
    if ejecucion.error:
        click.echo(f"Error: {ejecucion.error}", err=True)
    if ejecucion.estado == "error":
        sys.exit(1)


@tareas_cli.command("interrumpidas")
@click.option("--horas", type=float, default=None, help="Antigüedad mínima (por defecto EJECUCIONES_INTERRUMPIDAS_HORAS).")
def tareas_interrumpidas(horas: float | None) -> None:
    """Marca como interrumpidas las ejecuciones que siguen en curso tras HORAS."""
    horas = current_app.config["EJECUCIONES_INTERRUMPIDAS_HORAS"] if horas is None else horas
    ids = marcar_interrumpidas(horas)
    click.echo(f"Ejecuciones marcadas como interrumpidas: {len(ids)}")
    for ejecucion_id in ids:
        click.echo(f"  {ejecucion_id}")


@tareas_cli.command("purgar")
@click.option("--dias", type=float, default=None, help="Antigüedad mínima (por defecto EJECUCIONES_SIN_CAMBIOS_DIAS).")
def tareas_purgar(dias: float | None) -> None:
    """Borra las ejecuciones "sin cambios" terminadas hace más de DIAS (también se hace al arrancar)."""
    dias = current_app.config["EJECUCIONES_SIN_CAMBIOS_DIAS"] if dias is None else dias
    click.echo(f"Ejecuciones sin cambios borradas: {purgar_sin_cambios(dias)}")


@logs_cli.command("buscar")
@click.option("--modulo")
@click.option("--ejecucion", "ejecucion_id")
@click.option("--nivel", "nivel_minimo", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False))
@click.option("--dias", default=1, show_default=True)
@click.option("--limite", default=100, show_default=True)
@click.option("--json", "como_json", is_flag=True, help="Imprime cada evento como JSON.")
def logs_buscar(modulo, ejecucion_id, nivel_minimo, dias, limite, como_json) -> None:
    eventos = buscar_logs(current_app.config["LOG_DIR"], modulo=modulo, ejecucion_id=ejecucion_id, nivel_minimo=nivel_minimo, dias=dias, limite=limite)
    for e in reversed(eventos):
        if como_json:
            click.echo(json.dumps(e, ensure_ascii=False))
        else:
            click.echo(f"{e['ts'][:19]} {e['nivel']:<8} [{e['modulo']}] {e.get('evento') or ''} {e['mensaje']} "
                       f"{'usuario=' + e['usuario'] if e.get('usuario') else ''} {'ejecucion=' + e['ejecucion_id'] if e.get('ejecucion_id') else ''}".rstrip())


def instalar(app: Flask) -> None:
    for grupo in (usuarios_cli, modulos_cli, tareas_cli, logs_cli):
        app.cli.add_command(grupo)
