"""Tarea ``procesar``: toma los correos pendientes del buzón, los valida, archiva los adjuntos o
responde con el rechazo, y mueve cada correo a su subcarpeta.

Reglas de atomicidad del hub (docs/ARQUITECTURA.md#atomicidad) aplicadas aquí:

* Sin ``commit``: las filas se confirman junto con el estado final de la ejecución.
* Aislamiento por correo: un correo que falla se registra como ``error``, se mueve a ``Error``
  y la corrida sigue con los demás (la ejecución termina en ``advertencia``). La reversión total
  del núcleo queda solo para caídas reales.
* Efectos externos al final e idempotentes: primero se clasifica, después se guardan archivos
  (el archivador no duplica) o se responde, y **mover el correo es lo último**. Si la corrida se
  corta antes, el correo sigue en la bandeja de entrada y se reprocesa. En el peor caso se
  repite un correo de rechazo, nunca se pierde un corte.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.ejecuciones import ContextoEjecucion
from app.extensions import db

from . import configuracion, reglas
from .archivador import Archivador, ArchivoGuardado, sha256
from .buzon import (
    CARPETA_ERROR,
    CARPETA_IGNORADOS,
    CARPETA_PROCESADOS,
    CARPETA_RECHAZADOS,
    Buzon,
    BuzonEws,
    Correo,
)
from .models import Archivo
from .models import Correo as FilaCorreo
from .models import Empresa as FilaEmpresa

ASUNTO_RECHAZO = "RECHAZADO: Formato incorrecto en tu corte de caja"

# Jinja propio (y no render_template) para que la lógica no dependa de Flask; con autoescape,
# el asunto y los nombres de archivo que escribe el remitente no se interpretan como HTML.
_plantillas = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def crear_buzon(config: configuracion.Configuracion) -> Buzon:
    return BuzonEws(config.ews_servidor, config.ews_usuario, config.ews_contrasena, config.buzon, proxy=config.ews_proxy)


def crear_archivador(config: configuracion.Configuracion) -> Archivador:
    return Archivador(config.destino)


def empresas_activas() -> list[reglas.Empresa]:
    filas = FilaEmpresa.query.filter(FilaEmpresa.activa == True).order_by(FilaEmpresa.orden, FilaEmpresa.carpeta).all()  # noqa: E712
    return [reglas.Empresa(carpeta=f.carpeta, palabras_clave=f.lista_claves) for f in filas]


def html_rechazo(correo: Correo, errores: Sequence[reglas.Error], hoy: date, buzon_reenvio: str) -> str:
    return _plantillas.get_template("corte_caja/correo_rechazo.html").render(
        asunto=correo.asunto, errores=errores, hoy=hoy, buzon_reenvio=buzon_reenvio,
    )


def procesar(ctx: ContextoEjecucion) -> dict:
    """Tarea programada (``flask tareas ejecutar corte_caja procesar``) y botón del panel.

    Parámetro opcional ``hoy=AAAA-MM-DD`` para reprocesar como si fuera otra fecha."""
    config = configuracion.leer()
    empresas = empresas_activas()
    if not empresas:
        raise RuntimeError("No hay empresas activas en CORTE_CAJA_EMPRESAS: sin ellas se rechazaría todo.")
    hoy = date.fromisoformat(ctx.parametros["hoy"]) if ctx.parametros.get("hoy") else date.today()
    procesador = _Procesador(ctx, config, crear_buzon(config), crear_archivador(config), empresas, hoy)
    return procesador.ejecutar()


class _Procesador:
    def __init__(self, ctx, config, buzon: Buzon, archivador: Archivador, empresas, hoy: date) -> None:
        self.ctx = ctx
        self.config = config
        self.buzon = buzon
        self.archivador = archivador
        self.empresas = empresas
        self.hoy = hoy
        self.conteo = {estado: 0 for estado in FilaCorreo.ESTADOS}
        self.archivos_guardados = 0
        self.archivos_duplicados = 0

    def ejecutar(self) -> dict:
        log = self.ctx.log
        if self.config.simulacion:
            log.info("Modo simulación: no se responde, no se guarda ni se mueve nada", extra={"evento": "corte_caja.simulacion"})
        for correo in self._pendientes():
            try:
                self._procesar(correo)
            except Exception as exc:
                self._registrar_error(correo, exc)
        total = sum(self.conteo.values())
        if total == 0:
            self.ctx.estado = "sin_cambios"
        elif self.conteo[FilaCorreo.ERROR]:
            self.ctx.estado = "advertencia"
        return {
            "modo": self.config.modo,
            "correos": total,
            **self.conteo,
            "archivos_guardados": self.archivos_guardados,
            "archivos_duplicados": self.archivos_duplicados,
        }

    # ------------------------------------------------------------------------ entrada

    def _pendientes(self) -> list[Correo]:
        if not self.config.simulacion:
            return self.buzon.pendientes(self.config.lote, self.config.recibidos_desde)
        # En simulación nada sale de la bandeja de entrada: se avanza por fecha de recepción y
        # se saltan los ya simulados, para no registrar el mismo correo en cada corrida.
        ultimo = db.session.query(db.func.max(FilaCorreo.recibido)).filter(FilaCorreo.simulado == True).scalar()  # noqa: E712
        desde = max(d for d in (ultimo, self.config.recibidos_desde, datetime.min) if d is not None)
        vistos = {m for (m,) in db.session.query(FilaCorreo.message_id).filter(
            FilaCorreo.simulado == True, FilaCorreo.recibido >= desde)}  # noqa: E712
        return [c for c in self.buzon.pendientes(self.config.lote, desde) if c.message_id not in vistos]

    # ------------------------------------------------------------------------ un correo

    def _procesar(self, correo: Correo) -> None:
        if reglas.es_mensaje_automatico(correo.remitente, correo.encabezados):
            return self._ignorar(correo, "Mensaje automático (respuesta automática, rebote o lista): no se responde.")
        if not reglas.remitente_permitido(correo.remitente, self.config.dominios):
            return self._ignorar(correo, f"Remitente fuera de los dominios permitidos ({', '.join(self.config.dominios)}): no se responde.")

        clasificacion = reglas.clasificar(correo.asunto, [a.nombre for a in correo.adjuntos], self.empresas, self.hoy)
        if not clasificacion.valida:
            return self._rechazar(correo, clasificacion)
        self._archivar(correo, clasificacion)

    def _ignorar(self, correo: Correo, motivo: str) -> None:
        self._mover(correo, CARPETA_IGNORADOS)
        self._registrar(correo, FilaCorreo.IGNORADO, motivo=motivo)
        self.ctx.log.info("Correo ignorado", extra={"evento": "corte_caja.ignorado", "datos": {"asunto": correo.asunto, "motivo": motivo}})

    def _rechazar(self, correo: Correo, clasificacion: reglas.Clasificacion) -> None:
        if not self.config.simulacion:
            html = html_rechazo(correo, clasificacion.errores, self.hoy, self.config.buzon)
            self.buzon.responder(correo, ASUNTO_RECHAZO, html)
        self._mover(correo, CARPETA_RECHAZADOS)
        self._registrar(
            correo, FilaCorreo.RECHAZADO, motivo="\n".join(str(e) for e in clasificacion.errores),
            empresa=clasificacion.empresa, fecha_corte=clasificacion.fecha,
        )
        self.ctx.log.info("Correo rechazado", extra={"evento": "corte_caja.rechazado", "datos": {
            "asunto": correo.asunto, "errores": len(clasificacion.errores)}})

    def _archivar(self, correo: Correo, clasificacion: reglas.Clasificacion) -> None:
        partes = reglas.carpeta_destino(clasificacion.empresa, clasificacion.fecha)
        validos = set(clasificacion.adjuntos_validos)
        guardados: list[tuple[str, int, ArchivoGuardado]] = []
        for adjunto in correo.adjuntos:
            if adjunto.nombre not in validos:
                continue
            if not adjunto.contenido:
                raise ValueError(f"El adjunto '{adjunto.nombre}' está vacío.")
            nombre = reglas.nombre_seguro(adjunto.nombre)
            if self.config.simulacion:
                self.archivador.carpeta(partes)  # valida la ruta sin escribir
                guardado = ArchivoGuardado("/".join(partes), nombre, sha256(adjunto.contenido), duplicado=False)
            else:
                guardado = self.archivador.guardar(partes, nombre, adjunto.contenido)
            guardados.append((adjunto.nombre, len(adjunto.contenido), guardado))
        self._mover(correo, CARPETA_PROCESADOS)

        fila = self._registrar(correo, FilaCorreo.PROCESADO, empresa=clasificacion.empresa, fecha_corte=clasificacion.fecha)
        for original, tamano, g in guardados:
            fila.archivos.append(Archivo(
                nombre_original=original[:255], nombre_final=g.nombre, carpeta=g.carpeta,
                sha256=g.sha256, tamano=tamano, duplicado=g.duplicado,
            ))
            if g.duplicado:
                self.archivos_duplicados += 1
            else:
                self.archivos_guardados += 1
        self.ctx.log.info("Correo archivado", extra={"evento": "corte_caja.procesado", "datos": {
            "asunto": correo.asunto, "carpeta": "/".join(partes), "archivos": len(guardados),
            "duplicados": sum(1 for *_, g in guardados if g.duplicado)}})

    def _registrar_error(self, correo: Correo, exc: Exception) -> None:
        self.ctx.log.exception("Error al procesar un correo; se mueve a %s", CARPETA_ERROR,
                               extra={"evento": "corte_caja.error", "datos": {"asunto": correo.asunto}})
        try:
            self._mover(correo, CARPETA_ERROR)
        except Exception:
            self.ctx.log.exception("No se pudo mover el correo a %s; queda en la bandeja de entrada", CARPETA_ERROR,
                                   extra={"evento": "corte_caja.error_mover"})
        self._registrar(correo, FilaCorreo.ERROR, motivo=f"{type(exc).__name__}: {exc}"[:2000])

    # ------------------------------------------------------------------------ apoyo

    def _mover(self, correo: Correo, carpeta: str) -> None:
        if not self.config.simulacion:
            self.buzon.mover(correo, carpeta)

    def _registrar(self, correo: Correo, estado: str, motivo: str | None = None, empresa: str | None = None,
                   fecha_corte: date | None = None) -> FilaCorreo:
        fila = FilaCorreo(
            ejecucion_id=self.ctx.ejecucion_id, message_id=correo.message_id, asunto=correo.asunto[:500],
            remitente=correo.remitente[:320], recibido=correo.recibido, estado=estado, motivo=motivo,
            empresa=empresa, fecha_corte=fecha_corte, simulado=self.config.simulacion,
        )
        db.session.add(fila)
        self.conteo[estado] += 1
        return fila
