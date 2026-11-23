"""Interfaz común para registrar ejecuciones de automatizaciones.

Una ejecución guarda módulo, tarea, quién la inició (usuario o proceso), fechas,
estado, resultado y error. Mientras está en curso, su identificador se inyecta en
todos los logs emitidos (de cualquier logger), de modo que ``buscar_logs(ejecucion_id=...)``
devuelve la traza completa de esa corrida.

Uso dentro de un módulo::

    from app.core.ejecuciones import ejecucion

    with ejecucion("conciliacion", tarea="conciliar", usuario_id=current_user.id) as ctx:
        ctx.log.info("Leyendo estado de cuenta")
        ...
        ctx.resultado = {"partidas": 120, "diferencias": 2}

Los módulos no importan ``app.core.models``: reciben ``ResumenEjecucion`` (inmutable) de
:func:`ejecutar_tarea` y de :func:`ultimas_ejecuciones`.

Sin sesión web (tarea programada)::

    flask tareas ejecutar conciliacion conciliar --proceso tarea-programada-diaria

Procesos largos: hoy las tareas corren de forma síncrona (en la petición web o en el
proceso CLI). Cuando un módulo necesite procesos largos, el punto de conexión de una
cola (RQ, Celery, Dramatiq...) es :func:`ejecutar_tarea`: en lugar de invocar la
función directamente se encolaría ``(modulo_id, tarea, parametros, ejecucion_id)`` y el
worker llamaría a este mismo servicio. Ver ``docs/EJECUCIONES.md``.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterator

from app.core.logs import (
    establecer_ejecucion,
    establecer_usuario,
    get_logger,
    restablecer_ejecucion,
    restablecer_usuario,
    sanear_texto,
)
from flask import current_app
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.core.models import Ejecucion, Modulo, ahora_utc
from app.extensions import db

MAX_RESULTADO = 4000
MENSAJE_INTERRUMPIDA = (
    "Interrumpida: el proceso terminó antes de registrar el resultado (reinicio o caída del "
    "servidor). Revisar si la tarea dejó efectos externos a medias."
)


class TareaNoEncontrada(LookupError):
    pass


class ModuloDeshabilitado(RuntimeError):
    """El módulo está deshabilitado en el catálogo (o no figura en él): sus tareas no se ejecutan."""

    def __init__(self, modulo_id: str) -> None:
        self.modulo_id = modulo_id
        super().__init__(f"El módulo «{modulo_id}» está deshabilitado en el catálogo: no se ejecutan sus tareas.")


class EjecucionEnCurso(RuntimeError):
    """El módulo ya tiene una ejecución vigente: la nueva se rechaza sin ejecutarse (fail-fast)."""

    def __init__(self, modulo_id: str, en_curso: ResumenEjecucion | None) -> None:
        self.modulo_id = modulo_id
        self.en_curso = en_curso
        detalle = f" (ejecución {en_curso.id[:8]}, iniciada por {en_curso.iniciado_por})" if en_curso else ""
        super().__init__(f"El módulo «{modulo_id}» ya tiene una ejecución en curso{detalle}.")


@dataclass
class ContextoEjecucion:
    ejecucion_id: str
    modulo_id: str
    tarea: str
    log: logging.Logger
    parametros: dict[str, Any] = field(default_factory=dict)
    resultado: Any = None
    estado: str = "exito"  # la tarea puede marcar "advertencia"


@dataclass(frozen=True)
class ResumenEjecucion:
    """Vista de una ejecución para los módulos (DTO): no expone la fila ORM."""

    id: str
    modulo_id: str
    tarea: str
    estado: str
    inicio: datetime
    fin: datetime | None
    resultado: str | None
    error: str | None
    usuario_id: int | None
    iniciado_por: str

    @classmethod
    def desde_fila(cls, fila: Ejecucion) -> ResumenEjecucion:
        return cls(
            id=fila.id, modulo_id=fila.modulo_id, tarea=fila.tarea, estado=fila.estado,
            inicio=fila.inicio, fin=fila.fin, resultado=fila.resultado, error=fila.error,
            usuario_id=fila.usuario_id, iniciado_por=fila.iniciado_por,
        )

    def a_dict(self) -> dict[str, Any]:
        """Representación JSON (fechas UTC en ISO 8601 con sufijo Z)."""
        return {
            "id": self.id,
            "tarea": self.tarea,
            "estado": self.estado,
            "inicio": self.inicio.isoformat() + "Z",
            "fin": self.fin.isoformat() + "Z" if self.fin else None,
            "resultado": self.resultado,
            "error": self.error,
        }


def _serializar(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False, default=str)
    return sanear_texto(texto, MAX_RESULTADO)


@contextmanager
def ejecucion(
    modulo_id: str,
    tarea: str = "",
    usuario_id: int | None = None,
    proceso: str | None = None,
    parametros: dict[str, Any] | None = None,
) -> Iterator[ContextoEjecucion]:
    """Registra una ejecución y vincula sus logs. Relanza la excepción si la tarea falla.

    Ejecución exclusiva por módulo: lanza ``EjecucionEnCurso`` (sin ejecutar nada) si el módulo
    ya tiene una ejecución vigente. Ver :func:`_iniciar`.
    """
    ejecucion_id = _iniciar(modulo_id, tarea, usuario_id, proceso)

    token_ej = establecer_ejecucion(ejecucion_id)
    token_us = establecer_usuario(None if usuario_id else (f"proceso:{proceso}" if proceso else None))
    log = get_logger(modulo_id)
    ctx = ContextoEjecucion(ejecucion_id, modulo_id, tarea, log, dict(parametros or {}))
    log.info("Ejecución iniciada: %s", tarea or "(sin nombre)", extra={"evento": "ejecucion.inicio"})
    try:
        yield ctx
    except Exception as exc:
        db.session.rollback()
        fila = db.session.get(Ejecucion, ejecucion_id)
        fila.estado = "error"
        fila.fin = ahora_utc()
        fila.error = sanear_texto(f"{type(exc).__name__}: {exc}", 1000)
        db.session.commit()
        log.exception("Ejecución finalizada con error", extra={"evento": "ejecucion.error"})
        raise
    else:
        fila = db.session.get(Ejecucion, ejecucion_id)
        fila.estado = ctx.estado if ctx.estado in Ejecucion.ESTADOS_FINALES_TAREA else "exito"
        fila.fin = ahora_utc()
        fila.resultado = _serializar(ctx.resultado)
        db.session.commit()
        nivel = {"advertencia": logging.WARNING, "sin_cambios": logging.DEBUG}.get(fila.estado, logging.INFO)
        log.log(nivel, "Ejecución finalizada: %s", fila.estado, extra={"evento": "ejecucion.fin"})
    finally:
        restablecer_usuario(token_us)
        restablecer_ejecucion(token_ej)


def _en_curso(modulo_id: str) -> ResumenEjecucion | None:
    fila = Ejecucion.query.filter_by(modulo_id=modulo_id, estado="en_curso").first()
    return ResumenEjecucion.desde_fila(fila) if fila else None


def _rechazar(modulo_id: str, tarea: str, usuario_id: int | None, proceso: str | None) -> None:
    db.session.rollback()
    en_curso = _en_curso(modulo_id)
    get_logger(modulo_id).warning(
        "Ejecución omitida: el módulo ya tiene una en curso",
        extra={"evento": "ejecucion.omitida_por_concurrencia", "datos": {
            "tarea": tarea, "usuario_id": usuario_id, "proceso": proceso,
            "ejecucion_en_curso": en_curso.id if en_curso else None,
        }},
    )
    raise EjecucionEnCurso(modulo_id, en_curso)


def _iniciar(modulo_id: str, tarea: str, usuario_id: int | None, proceso: str | None) -> str:
    """Toma el mutex del módulo y registra la ejecución ``en_curso``. Devuelve su id.

    1. Una ejecución ``en_curso`` más antigua que ``EJECUCIONES_INTERRUMPIDAS_HORAS`` es un
       proceso muerto: se marca ``interrumpida`` y libera el paso (caso zombie).
    2. Si queda una vigente, se rechaza sin insertar (caso normal, sin tocar la base).
    3. La inserción es la que decide: el índice único filtrado
       ``ux_HUB_EJECUCIONES_modulo_en_curso`` hace fallar el segundo INSERT si dos procesos
       pasaron el paso 2 a la vez. Consultar y luego insertar no bastaría: con READ COMMITTED
       los dos verían el módulo libre.
    """
    horas = current_app.config["EJECUCIONES_INTERRUMPIDAS_HORAS"]
    marcar_interrumpidas(horas, modulo_id=modulo_id)
    if _en_curso(modulo_id) is not None:
        _rechazar(modulo_id, tarea, usuario_id, proceso)
    fila = Ejecucion(modulo_id=modulo_id, tarea=tarea, usuario_id=usuario_id, proceso=proceso, estado="en_curso")
    db.session.add(fila)
    try:
        db.session.commit()
    except IntegrityError:
        _rechazar(modulo_id, tarea, usuario_id, proceso)
    return fila.id


def ejecutar_tarea(
    modulo_id: str,
    tarea: str,
    usuario_id: int | None = None,
    proceso: str | None = None,
    parametros: dict[str, Any] | None = None,
) -> ResumenEjecucion:
    """Ejecuta una tarea declarada en ``DefinicionModulo.tareas``.

    No relanza excepciones de la tarea: quedan registradas en la ejecución y en los
    logs. Devuelve el ``ResumenEjecucion`` final. Sin crear ningún registro, lanza
    ``ModuloDeshabilitado`` si el módulo está deshabilitado en el catálogo (así deshabilitarlo
    también detiene sus tareas programadas) y ``EjecucionEnCurso`` si ya tiene una vigente.
    """
    from app.core.registro import registro

    definicion = registro().obtener(modulo_id)
    if definicion is None or tarea not in definicion.tareas:
        raise TareaNoEncontrada(f"{modulo_id}:{tarea}")
    _exigir_habilitado(modulo_id, tarea, usuario_id, proceso)
    funcion = definicion.tareas[tarea]
    ejecucion_id = None
    try:
        with ejecucion(modulo_id, tarea, usuario_id=usuario_id, proceso=proceso, parametros=parametros) as ctx:
            ejecucion_id = ctx.ejecucion_id
            retorno = funcion(ctx)
            if ctx.resultado is None:
                ctx.resultado = retorno
    except EjecucionEnCurso:
        if ejecucion_id is None:
            raise  # rechazada antes de iniciar: no hay registro que devolver
    except Exception:
        pass  # ya registrado
    return ResumenEjecucion.desde_fila(db.session.get(Ejecucion, ejecucion_id))


def _exigir_habilitado(modulo_id: str, tarea: str, usuario_id: int | None, proceso: str | None) -> None:
    fila = db.session.get(Modulo, modulo_id)
    if fila is not None and fila.activo:
        return
    get_logger(modulo_id).warning(
        "Ejecución omitida: el módulo está deshabilitado",
        extra={"evento": "ejecucion.omitida_modulo_deshabilitado", "datos": {
            "tarea": tarea, "usuario_id": usuario_id, "proceso": proceso, "en_catalogo": fila is not None,
        }},
    )
    raise ModuloDeshabilitado(modulo_id)


def marcar_interrumpidas(horas: float, modulo_id: str | None = None) -> list[str]:
    """Marca como ``interrumpida`` las ejecuciones ``en_curso`` que empezaron hace más de ``horas``.

    Una ejecución queda ``en_curso`` para siempre si el proceso muere antes de registrar el
    resultado. Solo se tocan las antiguas porque ``create_app`` también corre en cada comando
    ``flask`` y en el recargador: marcar todas cortaría corridas reales de otro proceso. Si una
    tarea marcada termina después, ``ejecucion()`` registra su resultado real encima.

    Con ``modulo_id`` solo revisa ese módulo (lo usa el mutex al iniciar una ejecución).
    """
    limite = ahora_utc() - timedelta(hours=horas)
    consulta = Ejecucion.query.filter(Ejecucion.estado == "en_curso", Ejecucion.inicio < limite)
    if modulo_id is not None:
        consulta = consulta.filter(Ejecucion.modulo_id == modulo_id)
    filas = consulta.all()
    if not filas:
        return []
    fin = ahora_utc()
    for fila in filas:
        fila.estado = "interrumpida"
        fila.fin = fin
        fila.error = MENSAJE_INTERRUMPIDA
    db.session.commit()
    ids = [f.id for f in filas]
    get_logger("core").warning(
        "Ejecuciones marcadas como interrumpidas: %s", len(ids),
        extra={"evento": "ejecucion.interrumpida", "datos": {"ejecuciones": ids, "horas": horas}},
    )
    return ids


def purgar_sin_cambios(dias: float) -> int:
    """Borra las ejecuciones ``sin_cambios`` terminadas hace más de ``dias``. Devuelve cuántas.

    Una tarea programada cada pocos minutos genera cientos de corridas diarias sin nada que
    procesar: sirven para saber que el programador está vivo, no como historial."""
    limite = ahora_utc() - timedelta(days=dias)
    borradas = Ejecucion.query.filter(Ejecucion.estado == "sin_cambios", Ejecucion.fin < limite).delete(
        synchronize_session=False
    )
    db.session.commit()
    if borradas:
        get_logger("core").info(
            "Ejecuciones sin cambios purgadas: %s", borradas,
            extra={"evento": "ejecucion.purga", "datos": {"borradas": borradas, "dias": dias}},
        )
    return borradas


def mantenimiento_al_iniciar(app) -> None:
    """Al arrancar: marca las interrumpidas y purga las ``sin_cambios`` antiguas, solo si las
    migraciones ya se aplicaron. Nunca impide el arranque."""
    with app.app_context():
        try:
            if inspect(db.engine).has_table(Ejecucion.__tablename__):
                marcar_interrumpidas(app.config["EJECUCIONES_INTERRUMPIDAS_HORAS"])
                purgar_sin_cambios(app.config["EJECUCIONES_SIN_CAMBIOS_DIAS"])
        except Exception:
            db.session.rollback()
            get_logger("core").exception(
                "No se pudo hacer el mantenimiento de ejecuciones al iniciar",
                extra={"evento": "ejecucion.error_limpieza"},
            )


def ultimas_ejecuciones(
    modulo_id: str, usuario_id: int | None = None, limite: int = 10, incluir_sin_cambios: bool = False,
) -> list[ResumenEjecucion]:
    """Ejecuciones más recientes de un módulo, opcionalmente solo las de un usuario.

    Omite las ``sin_cambios`` salvo que se pidan: son corridas sin nada que procesar."""
    consulta = Ejecucion.query.filter_by(modulo_id=modulo_id)
    if not incluir_sin_cambios:
        consulta = consulta.filter(Ejecucion.estado != "sin_cambios")
    if usuario_id is not None:
        consulta = consulta.filter_by(usuario_id=usuario_id)
    filas = consulta.order_by(Ejecucion.inicio.desc()).limit(limite).all()
    return [ResumenEjecucion.desde_fila(f) for f in filas]
