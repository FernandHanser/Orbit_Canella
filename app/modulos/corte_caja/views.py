"""Tablero del corte de caja: pestañas Procesadas, Rechazadas y Cuadre mensual, y el detalle.

Traslado del tablero del prototipo (``index.html``) a la plantilla del hub: el menú lateral del
prototipo es aquí una fila de pestañas. Sin decoradores de seguridad: el núcleo exige sesión y el
permiso del módulo en todas las rutas de este Blueprint.

No hay botón para revisar el buzón: lo hace la tarea programada (docs/PLAN_INTEGRACION_CORTE_DE_CAJA.md).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, abort, render_template, request
from sqlalchemy.orm import selectinload

from app.core.logs import get_logger
from app.core.paginacion import POR_PAGINA, pagina_actual
from app.core.permisos import es_administrador
from app.extensions import db

from . import cuadre
from .models import Archivo, Caja, Correo

bp = Blueprint("corte_caja", __name__, template_folder="templates")
log = get_logger("corte_caja")

PESTANAS = (
    ("procesadas", "Procesadas", "circle-check", "green"),
    ("rechazadas", "Rechazadas", "mail-x", "red"),
    ("cuadre", "Cuadre mensual", "calendar-check", "blue"),
)
# Como en el prototipo: la tabla de procesadas muestra los guardados y los que fallaron.
ESTADOS_PROCESADAS = (Correo.PROCESADO, Correo.ERROR)
MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")


def _fecha(nombre: str) -> date | None:
    try:
        return date.fromisoformat(request.args.get(nombre, ""))
    except ValueError:
        return None


def _utc(dia: date, hora: time) -> datetime:
    """Inicio o fin de un día local expresado en UTC sin zona (como se guarda ``recibido``)."""
    return datetime.combine(dia, hora).astimezone().astimezone(timezone.utc).replace(tzinfo=None)


def _dia_local(recibido: datetime) -> date:
    return recibido.replace(tzinfo=timezone.utc).astimezone().date()


def _reales():
    """Correos del tablero: sin las filas que dejó el modo simulación (retirado)."""
    return Correo.query.filter(Correo.simulado == False)  # noqa: E712


def _cajas() -> list[cuadre.CajaDirectorio]:
    return [cuadre.CajaDirectorio(c.nombre_caja, c.correo)
            for c in Caja.query.order_by(Caja.categoria, Caja.nombre_caja)]


def _filtro_texto_y_fechas(consulta):
    filtro = {"texto": (request.args.get("texto") or "").strip(), "desde": _fecha("desde"), "hasta": _fecha("hasta")}
    if filtro["desde"]:
        consulta = consulta.filter(Correo.recibido >= _utc(filtro["desde"], time.min))
    if filtro["hasta"]:
        consulta = consulta.filter(Correo.recibido <= _utc(filtro["hasta"], time.max))
    return consulta, filtro


@bp.route("/")
def inicio():
    pestana = request.args.get("pestana") or "procesadas"
    if pestana not in {p[0] for p in PESTANAS}:
        pestana = "procesadas"
    conteos = dict(db.session.query(Correo.estado, db.func.count(Correo.id))
                   .filter(Correo.simulado == False).group_by(Correo.estado).all())  # noqa: E712
    kpis = {"aceptadas": conteos.get(Correo.PROCESADO, 0), "rechazadas": conteos.get(Correo.RECHAZADO, 0),
            "tiendas": Caja.query.count()}
    contexto = {"pestana": pestana, "pestanas": PESTANAS, "kpis": kpis}
    if pestana == "procesadas":
        contexto.update(_procesadas())
    elif pestana == "rechazadas":
        contexto.update(_rechazadas())
    else:
        contexto.update(_cuadre())
    return render_template("corte_caja/inicio.html", **contexto)


def _procesadas() -> dict:
    consulta, filtro = _filtro_texto_y_fechas(_reales().filter(Correo.estado.in_(ESTADOS_PROCESADAS)))
    if filtro["texto"]:
        patron = f"%{filtro['texto'].lower()}%"
        con_archivo = db.session.query(Archivo.correo_id).filter(db.func.lower(Archivo.nombre_original).like(patron))
        consulta = consulta.filter(db.or_(
            db.func.lower(Correo.asunto).like(patron), db.func.lower(Correo.remitente).like(patron),
            db.func.lower(Correo.adjuntos).like(patron), Correo.id.in_(con_archivo)))
    pagina = (consulta.options(selectinload(Correo.archivos))
              .order_by(Correo.recibido.desc(), Correo.id.desc())
              .paginate(page=pagina_actual(), per_page=POR_PAGINA, error_out=False))
    return {"pagina": pagina, "correos": pagina.items, "filtro": filtro}


def _rechazadas() -> dict:
    cajas = _cajas()
    consulta, filtro = _filtro_texto_y_fechas(_reales().filter(Correo.estado == Correo.RECHAZADO))
    if filtro["texto"]:
        texto = filtro["texto"].lower()
        patron = f"%{texto}%"
        # «Buscar por caja»: los correos de las cajas cuyo nombre coincide con lo escrito.
        remitentes = set().union(*(cuadre.correos(c.correo) for c in cajas if texto in c.nombre.lower()))
        consulta = consulta.filter(db.or_(
            db.func.lower(Correo.asunto).like(patron), db.func.lower(Correo.remitente).like(patron),
            db.func.lower(Correo.remitente).in_(remitentes) if remitentes else db.false()))
    pagina = consulta.order_by(Correo.recibido.desc(), Correo.id.desc()).paginate(
        page=pagina_actual(), per_page=POR_PAGINA, error_out=False)
    caja_por_id = {c.id: cuadre.caja_de(c.remitente, c.asunto, cajas) for c in pagina.items}
    return {"pagina": pagina, "correos": pagina.items, "filtro": filtro, "caja_por_id": caja_por_id}


def _mes_pedido(hoy: date) -> tuple[int, int]:
    try:
        anio, mes = (int(p) for p in (request.args.get("mes") or "").split("-"))
        date(anio, mes, 1)
        return anio, mes
    except ValueError:
        return hoy.year, hoy.month


def _registros_del_mes(anio: int, mes: int) -> dict[date, list[cuadre.Registro]]:
    inicio = date(anio, mes, 1)
    fin = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    filas = (_reales().filter(Correo.estado.in_((Correo.PROCESADO, Correo.SIN_MOVIMIENTO)))
             .filter(db.or_(Correo.fecha_corte.between(inicio, fin),
                            db.and_(Correo.fecha_corte.is_(None),
                                    Correo.recibido.between(_utc(inicio, time.min) - timedelta(days=1),
                                                            _utc(fin, time.max) + timedelta(days=1)))))
             .options(selectinload(Correo.archivos)).all())
    por_dia: dict[date, list[cuadre.Registro]] = {}
    for f in filas:
        # Sin fecha del corte (un «sin movimiento» sin fecha en el asunto): el día en que llegó.
        dia = f.fecha_corte or _dia_local(f.recibido)
        if dia.year == anio and dia.month == mes:
            por_dia.setdefault(dia, []).append(cuadre.Registro(
                fecha=dia, estado=cuadre.SIN_MOVIMIENTO if f.estado == Correo.SIN_MOVIMIENTO else cuadre.RECIBIDO,
                remitente=f.remitente, asunto=f.asunto, destino=" ".join(a.carpeta for a in f.archivos)))
    return por_dia


def _cuadre() -> dict:
    hoy = date.today()
    anio, mes = _mes_pedido(hoy)
    dia = _fecha("dia")
    if dia is None or (dia.year, dia.month) != (anio, mes):
        dia = cuadre.dia_inicial(anio, mes, hoy)
    por_dia = _registros_del_mes(anio, mes)
    calendario = [[(d, cuadre.estado_del_dia(d, por_dia.get(d, []), hoy)) if d else None for d in semana]
                  for semana in cuadre.semanas(anio, mes)]
    filas = Caja.query.order_by(Caja.categoria, Caja.nombre_caja).all()
    del_dia = por_dia.get(dia, [])
    estados = [(c, cuadre.estado_de_la_caja(cuadre.CajaDirectorio(c.nombre_caja, c.correo), del_dia)) for c in filas]
    resumen = {e: sum(1 for _, x in estados if x == e) for e in (cuadre.RECIBIDO, cuadre.SIN_MOVIMIENTO, cuadre.NO_RECIBIDO)}
    anterior = (date(anio, mes, 1) - timedelta(days=1))
    siguiente = (date(anio, mes, 28) + timedelta(days=4)).replace(day=1)
    return {
        "mes": f"{anio:04d}-{mes:02d}", "titulo_mes": f"{MESES[mes - 1]} {anio}", "dia": dia,
        "calendario": calendario, "estados": estados, "resumen": resumen,
        "mes_anterior": f"{anterior:%Y-%m}", "mes_siguiente": f"{siguiente:%Y-%m}",
    }


@bp.route("/correos/<int:correo_id>")
def detalle(correo_id: int):
    correo = db.session.get(Correo, correo_id) or abort(404)
    # El enlace a la ejecución lleva a Administración: solo se muestra a quien puede abrirla.
    return render_template("corte_caja/detalle.html", correo=correo, ver_ejecucion=es_administrador())
