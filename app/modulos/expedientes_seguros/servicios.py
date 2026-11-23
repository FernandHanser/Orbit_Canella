"""Casos de uso: buscar la llamada, servir páginas, armar el paquete y preparar o enviar el correo.

Archivos de trabajo en ``<instance>/expedientes_seguros/``:

* ``miniaturas/<sha del original>/<página>_<ancho>.jpg``: se generan una vez por página.
* ``paquetes/<id>/``: PDF armados, para descargarlos y para el ``.eml``. Se borran a los
  ``EXPEDIENTES_RETENCION_DIAS`` (contienen datos personales: DPI, tarjeta de circulación).

El original de SAP solo se lee; se guarda en memoria un momento para no releerlo de la red en
cada miniatura.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from flask import current_app

from app.core.logs import get_logger
from app.extensions import db

from . import configuracion, documentos, reglas
from .envio import CorreoNoEnviado, Enviador, EnviadorSmtp
from .models import Aseguradora, CodigoAseguradora, Paquete, Parametro
from .sap import Anexo, Llamada, Pendiente, RepositorioSap, SapSql

log = get_logger("expedientes_seguros")

PARAMETROS = ("para", "cc", "asunto", "cuerpo")
_ORIGINALES_EN_MEMORIA = 4


def crear_repositorio() -> RepositorioSap:
    return SapSql(configuracion.sap())


def directorio_trabajo() -> Path:
    ruta = Path(current_app.instance_path) / "expedientes_seguros"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


# ------------------------------------------------------------------------------ llamada

def buscar(call_id: int, ceco: str) -> tuple[Llamada | None, str | None]:
    """La llamada si existe y es de ese centro de costo; si no, el motivo para mostrar."""
    llamada = crear_repositorio().buscar_llamada(call_id)
    if llamada is None:
        return None, f"La llamada de servicio {call_id} no existe en SAP."
    if ceco and llamada.ceco != ceco:
        destino = f"{llamada.ceco} {llamada.ceco_nombre}".strip() or "ninguno"
        return None, f"La llamada {call_id} no pertenece al centro de costo {ceco} (es del {destino})."
    if not llamada.anexos:
        return None, f"La llamada {call_id} no tiene el expediente en PDF en sus anexos de SAP."
    return llamada, None


_anexos: dict[tuple[int, int], tuple[float, str]] = {}
_ANEXO_VIGENCIA_S = 3600


def ruta_anexo(call_id: int, linea: int) -> str | None:
    """Ruta del anexo sin volver a SAP en cada miniatura (se recuerda una hora)."""
    clave = (call_id, linea)
    guardado = _anexos.get(clave)
    if guardado and time.time() - guardado[0] < _ANEXO_VIGENCIA_S:
        return guardado[1]
    llamada = crear_repositorio().buscar_llamada(call_id)
    encontrado = next((a for a in (llamada.anexos if llamada else ()) if a.linea == linea), None)
    if encontrado is None:
        return None
    _anexos[clave] = (time.time(), encontrado.ruta)
    return encontrado.ruta


def bloques_de(llamada: Llamada) -> list[Anexo]:
    """Los anexos que forman el expediente combinado que ve y arma Caja: el más reciente de los
    que no son DPI (si Taller volvió a subir el PDF corregido, el anterior ya no cuenta) más cada
    DPI a color de la llamada (no reemplaza nada: es un documento aparte, ver ``reglas.es_dpi``).
    El expediente va siempre primero."""
    no_dpi = [a for a in llamada.anexos if not reglas.es_dpi(a.nombre)]
    dpi = [a for a in llamada.anexos if reglas.es_dpi(a.nombre)]
    principal = [no_dpi[-1]] if no_dpi else list(llamada.anexos[-1:])
    bloques = principal + dpi
    for a in bloques:
        _anexos[(llamada.call_id, a.linea)] = (time.time(), a.ruta)
    return bloques


def paginas_combinadas(bloques: list[Anexo]) -> tuple[list[dict], dict[int, tuple[int, int]]]:
    """Para el expediente combinado: una sección por anexo (línea, nombre, fecha, página inicial y
    final en la numeración combinada) y el mapa página combinada → (línea, página local), para
    pedir la miniatura correcta y, al generar, tomar cada hoja de su archivo de origen."""
    secciones = []
    bloque_a_cantidad = []
    for a in bloques:
        cantidad = documentos.contar_paginas(original(a.ruta))
        bloque_a_cantidad.append((a.linea, cantidad))
    mapa = reglas.mapa_paginas(bloque_a_cantidad)
    n = 0
    for a, (_, cantidad) in zip(bloques, bloque_a_cantidad):
        secciones.append({"linea": a.linea, "nombre": a.nombre, "fecha": a.fecha,
                           "inicio": n + 1, "fin": n + cantidad})
        n += cantidad
    return secciones, mapa


# ------------------------------------------------------------------------ original y páginas

_originales: "OrderedDict[str, tuple[float, bytes]]" = OrderedDict()
_candado = threading.Lock()


def original(ruta: str) -> bytes:
    """Bytes del PDF de SAP; en memoria mientras no cambie en el servidor de archivos."""
    ruta = reglas.ruta_accesible(ruta, configuracion.servidor_anexos())
    try:
        modificado = os.stat(ruta).st_mtime
    except OSError as exc:
        raise FileNotFoundError(f"No se encontró el expediente en {ruta}: {exc.strerror or exc}") from exc
    with _candado:
        guardado = _originales.get(ruta)
        if guardado and guardado[0] == modificado:
            _originales.move_to_end(ruta)
            return guardado[1]
    datos = documentos.leer(ruta)
    with _candado:
        _originales[ruta] = (modificado, datos)
        while len(_originales) > _ORIGINALES_EN_MEMORIA:
            _originales.popitem(last=False)
    return datos


def imagen(ruta: str, pagina: int, ancho: int) -> bytes:
    datos = original(ruta)
    archivo = directorio_trabajo() / "miniaturas" / documentos.sha256(datos) / f"{pagina}_{ancho}.jpg"
    if archivo.exists():
        return archivo.read_bytes()
    jpg = documentos.imagen_pagina(datos, pagina, ancho)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_bytes(jpg)
    return jpg


# ------------------------------------------------------------------------------- bandeja

DIAS_ATENCION = 2     # desde aquí la antigüedad se marca en amarillo
DIAS_URGENTE = 4      # y desde aquí en rojo (control de fechas de recepción, RF-09)


@dataclass(frozen=True)
class FilaBandeja:
    pendiente: Pendiente
    dias: int

    @property
    def color(self) -> str:
        return "red" if self.dias >= DIAS_URGENTE else "yellow" if self.dias >= DIAS_ATENCION else "green"


def bandeja(ceco: str, hoy: date | None = None) -> list[FilaBandeja]:
    """Pendientes de armar: llamadas activas del centro de costo sin paquete generado en el hub. La
    antigüedad se cuenta desde que se abrió la llamada.

    El cruce con los paquetes se hace aquí porque SAP y el hub están en bases distintas."""
    hoy = hoy or date.today()
    candidatas = crear_repositorio().pendientes(ceco)
    if not candidatas:
        return []
    armadas = {c for (c,) in db.session.query(Paquete.call_id).filter(
        Paquete.call_id.in_([p.call_id for p in candidatas])).distinct()}
    return [FilaBandeja(p, max((hoy - p.creada).days, 0)) for p in candidatas if p.call_id not in armadas]


# ------------------------------------------------------------------------------- correo

def parametros() -> dict[str, str]:
    guardados = {p.clave: p.valor for p in Parametro.query.all()}
    return {clave: guardados.get(clave, "") for clave in PARAMETROS}


def aseguradora_de(codigo: str) -> Aseguradora | None:
    fila = db.session.get(CodigoAseguradora, codigo) if codigo else None
    return fila.aseguradora if fila and fila.aseguradora.activa else None


def plantilla(aseguradora: Aseguradora | None) -> dict[str, str]:
    """Para, CC, asunto y cuerpo: los de la aseguradora y, donde los deja vacíos, los del módulo."""
    base = parametros()
    if aseguradora is None:
        return base
    return {clave: (getattr(aseguradora, clave) or "").strip() or base[clave] for clave in PARAMETROS}


def checklist(aseguradora: Aseguradora | None) -> list[dict]:
    """Documentos que Créditos pide a esa aseguradora, en su orden (vacío si no está configurada)."""
    if aseguradora is None:
        return []
    return [{"id": d.id, "nombre": d.nombre, "obligatorio": d.obligatorio, "es_factura": reglas.es_factura(d.nombre),
             "separado": d.separado} for d in aseguradora.documentos if d.activo]


def datos_plantilla(llamada: Llamada, serie: str, numero: str) -> dict[str, str]:
    return {
        "aseguradora": llamada.aseguradora_nombre, "serie": serie, "numero": numero,
        "reclamo": llamada.reclamo, "poliza": llamada.poliza,
        "llamada": str(llamada.call_id), "orden": str(llamada.orden),
    }


def correo_sugerido(llamada: Llamada) -> dict[str, str]:
    """Correo prellenado para el visor; Caja lo revisa y puede cambiarlo antes de generar."""
    aseguradora = aseguradora_de(llamada.aseguradora_codigo)
    serie = llamada.factura.serie if llamada.factura else ""
    numero = llamada.factura.numero if llamada.factura else ""
    base = plantilla(aseguradora)
    datos = datos_plantilla(llamada, serie, numero)
    return {
        "para": base["para"], "cc": base["cc"],
        "asunto": reglas.aplicar_plantilla(base["asunto"], datos),
        "cuerpo": reglas.aplicar_plantilla(base["cuerpo"], datos),
        "serie": serie, "numero": numero,
        "factura_separada": bool(aseguradora and aseguradora.factura_separada),
        "aseguradora_configurada": aseguradora is not None,
    }


# ------------------------------------------------------------------------------ paquete

@dataclass(frozen=True)
class Solicitud:
    paginas: list[int]
    serie: str
    numero: str
    para: str
    cc: str
    asunto: str
    cuerpo: str
    factura: bytes | None
    factura_separada: bool
    abierto_en: float | None       # epoch del visor, para medir el tiempo de armado
    # Página → ids de documento asignados (una página puede tener varios); documento (id → nombre)
    # de los que están marcados «archivo aparte» en el checklist. Con esto se arma, además del PDF
    # principal, un PDF propio por cada documento aparte que tenga al menos una página elegida.
    asignaciones: Mapping[int, object] = field(default_factory=dict)
    documentos_aparte: Mapping[int, str] = field(default_factory=dict)
    checklist: list | None = None  # resultado de reglas.evaluar_checklist, para el registro


def carpeta_paquete(paquete_id: int) -> Path:
    return directorio_trabajo() / "paquetes" / str(paquete_id)


def _armar_combinado(fuentes: dict[int, bytes], mapa: dict[int, tuple[int, int]], bloques: list[Anexo],
                      paginas: list[int], anteponer: bytes | None = None) -> bytes:
    """Arma un PDF con ``paginas`` (combinadas) tomando cada una de su anexo de origen, en el orden
    de ``bloques`` (expediente antes que DPI); ``anteponer`` (la factura unida) va primero."""
    por_linea = reglas.paginas_por_linea(paginas, mapa)
    piezas = [anteponer] if anteponer else []
    for a in bloques:
        locales = por_linea.get(a.linea)
        if locales:
            piezas.append(documentos.armar(fuentes[a.linea], locales))
    return documentos.concatenar(piezas)


def armar_paquete(llamada: Llamada, solicitud: Solicitud, usuario_id: int) -> Paquete:
    """Genera los PDF, los deja en la carpeta del paquete y registra quién armó qué.

    El expediente se combina con el DPI a color de la llamada cuando lo trae (``bloques_de``): el
    cajero elige páginas de ambos como si fueran un solo documento. Un documento del checklist
    marcado «archivo aparte» sale en su propio PDF (``nombre_documento_separado``); sus páginas no
    se quitan del principal si alguna también está asignada a un documento que va unido (se
    copian, no se recortan: ver ``reglas.separar_por_documento``). La factura que Caja sube es
    aparte: no viene de páginas de SAP, sigue su propio mecanismo."""
    bloques = bloques_de(llamada)
    secciones, mapa = paginas_combinadas(bloques)
    total = len(mapa)
    fuentes = {a.linea: original(a.ruta) for a in bloques}

    principal, por_documento = reglas.separar_por_documento(
        solicitud.paginas, solicitud.asignaciones, solicitud.documentos_aparte)
    unida = solicitud.factura if solicitud.factura and not solicitud.factura_separada else None
    pdf = _armar_combinado(fuentes, mapa, bloques, principal, anteponer=unida)
    nombre = reglas.nombre_paquete(llamada.call_id, llamada.aseguradora_nombre, date.today())

    principal_anexo, dpi_anexo = bloques[0], (bloques[1] if len(bloques) > 1 else None)
    paquete = Paquete(
        call_id=llamada.call_id, orden=llamada.orden, ceco=llamada.ceco,
        aseguradora_codigo=llamada.aseguradora_codigo, aseguradora_nombre=llamada.aseguradora_nombre[:150],
        reclamo=llamada.reclamo[:60], poliza=llamada.poliza[:60],
        factura_serie=solicitud.serie[:60], factura_numero=solicitud.numero[:60],
        anexo=principal_anexo.ruta[:500], anexo_sha256=documentos.sha256(fuentes[principal_anexo.linea]),
        anexo_dpi=dpi_anexo.ruta[:500] if dpi_anexo else None,
        anexo_dpi_sha256=documentos.sha256(fuentes[dpi_anexo.linea]) if dpi_anexo else None,
        paginas=reglas.rangos(solicitud.paginas)[:1000], cantidad_paginas=len(solicitud.paginas), total_paginas=total,
        nombre_archivo=nombre, factura_separada=solicitud.factura_separada, con_factura=solicitud.factura is not None,
        para=solicitud.para[:1000], cc=solicitud.cc[:1000], asunto=solicitud.asunto[:300],
        segundos_armado=int(time.time() - solicitud.abierto_en) if solicitud.abierto_en else None,
        checklist=json.dumps(solicitud.checklist, ensure_ascii=False) if solicitud.checklist else None,
        usuario_id=usuario_id,
    )
    db.session.add(paquete)
    db.session.flush()   # para tener el id de la carpeta

    carpeta = carpeta_paquete(paquete.id)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / nombre).write_bytes(pdf)
        if solicitud.factura and solicitud.factura_separada:
            (carpeta / reglas.nombre_factura(llamada.call_id, llamada.aseguradora_nombre)).write_bytes(solicitud.factura)
        for doc_id, paginas_doc in por_documento.items():
            archivo_doc = _armar_combinado(fuentes, mapa, bloques, paginas_doc)
            nombre_doc = reglas.nombre_documento_separado(
                llamada.call_id, llamada.aseguradora_nombre, solicitud.documentos_aparte[doc_id])
            (carpeta / nombre_doc).write_bytes(archivo_doc)
        (carpeta / "cuerpo.txt").write_text(solicitud.cuerpo, encoding="utf-8")
        db.session.commit()
    except Exception:
        db.session.rollback()
        shutil.rmtree(carpeta, ignore_errors=True)
        raise
    log.info("Paquete armado", extra={"evento": "expedientes.paquete", "datos": {
        "paquete": paquete.id, "llamada": llamada.call_id, "aseguradora": llamada.aseguradora_codigo,
        "paginas": paquete.cantidad_paginas, "de": total, "factura": paquete.con_factura,
        "segundos": paquete.segundos_armado,
        "faltantes": reglas.faltantes(solicitud.checklist or [])}})
    purgar_antiguos()
    return paquete


def checklist_de(paquete: Paquete) -> list[dict]:
    return json.loads(paquete.checklist) if paquete.checklist else []


def adjuntos_de(paquete: Paquete) -> list[reglas.Adjunto]:
    """El paquete principal primero y, después, cualquier otro PDF de la carpeta: la factura que
    Caja subió aparte (``FAC ...``) y los documentos del checklist marcados «archivo aparte»."""
    carpeta = carpeta_paquete(paquete.id)
    principal = carpeta / paquete.nombre_archivo
    if not principal.exists():
        return []
    archivos = [reglas.Adjunto(paquete.nombre_archivo, principal.read_bytes())]
    extras = sorted(p for p in carpeta.glob("*.pdf") if p.name != paquete.nombre_archivo)
    archivos += [reglas.Adjunto(p.name, p.read_bytes()) for p in extras]
    return archivos


def eml(paquete: Paquete) -> bytes | None:
    adjuntos = adjuntos_de(paquete)
    if not adjuntos:
        return None
    cuerpo_txt = carpeta_paquete(paquete.id) / "cuerpo.txt"
    cuerpo = cuerpo_txt.read_text(encoding="utf-8") if cuerpo_txt.exists() else ""
    return reglas.correo_eml(paquete.para, paquete.cc, paquete.asunto, cuerpo, adjuntos)


MODO_PRUEBA, MODO_PRODUCCION = "prueba", "produccion"
DESTINO_PRUEBA = '"Caja Taller1" <cajamauto2@canella.com.gt>'


@dataclass(frozen=True)
class ModoEnvio:
    modo: str
    destino_prueba: str

    @property
    def prueba(self) -> bool:
        return self.modo != MODO_PRODUCCION


def modo_envio() -> ModoEnvio:
    """En prueba (lo predeterminado) todo correo va solo al destino de prueba: así se ensaya el
    módulo sin escribirle a Cobros. Producción solo si un administrador lo cambia."""
    guardados = {p.clave: p.valor for p in Parametro.query.filter(
        Parametro.clave.in_(("envio_modo", "envio_destino_prueba")))}
    modo = MODO_PRODUCCION if guardados.get("envio_modo") == MODO_PRODUCCION else MODO_PRUEBA
    return ModoEnvio(modo, (guardados.get("envio_destino_prueba") or "").strip() or DESTINO_PRUEBA)


def guardar_modo_envio(modo: str, destino_prueba: str) -> None:
    for clave, valor in (("envio_modo", modo), ("envio_destino_prueba", destino_prueba)):
        fila = db.session.get(Parametro, clave) or Parametro(clave=clave)
        fila.valor = valor
        db.session.add(fila)
    db.session.commit()


def crear_enviador() -> Enviador:
    return EnviadorSmtp(configuracion.correo())


def enviar(paquete: Paquete, usuario_id: int, responder_a: str | None = None) -> str | None:
    """Envía el paquete desde el buzón del hub con los adjuntos y el correo que Caja revisó al
    generar. Una sola vez: el paquete se marca antes de enviar (con un ``UPDATE`` condicional, para
    que un doble clic no lo mande dos veces) y se desmarca si el servidor no lo acepta.

    En modo prueba va solo al destino de prueba, sin CC, con ``[PRUEBA]`` en el asunto y los
    destinatarios reales al inicio del cuerpo; no marca el paquete, para poder enviarlo de verdad
    después. Devuelve el destino de prueba usado, o ``None`` si se envió en producción."""
    adjuntos = adjuntos_de(paquete)
    if not adjuntos:
        raise CorreoNoEnviado("Los archivos del paquete ya se borraron; vuelve a generarlo desde la llamada.")
    enviador = crear_enviador()
    remitente = configuracion.correo().remitente
    cuerpo_txt = carpeta_paquete(paquete.id) / "cuerpo.txt"
    cuerpo = cuerpo_txt.read_text(encoding="utf-8") if cuerpo_txt.exists() else ""
    modo = modo_envio()

    if modo.prueba:
        aviso = (f"*** CORREO DE PRUEBA (AUTOMATE) ***\nEn producción iría a:\n  Para: {paquete.para}\n"
                 f"  CC: {paquete.cc or '—'}\n{'*' * 35}\n\n")
        enviador.enviar(reglas.correo_saliente(remitente, modo.destino_prueba, "", f"[PRUEBA] {paquete.asunto}",
                                               aviso + cuerpo, adjuntos, responder_a=responder_a))
        log.info("Correo de prueba enviado", extra={"evento": "expedientes.correo_prueba", "datos": {
            "paquete": paquete.id, "llamada": paquete.call_id, "destino": modo.destino_prueba,
            "para_real": paquete.para, "cc_real": paquete.cc}})
        return modo.destino_prueba

    mensaje = reglas.correo_saliente(remitente, paquete.para, paquete.cc, paquete.asunto, cuerpo, adjuntos,
                                     responder_a=responder_a)
    marcado = db.session.query(Paquete).filter(Paquete.id == paquete.id, Paquete.enviado_en.is_(None)).update(
        {Paquete.enviado_en: _ahora(), Paquete.enviado_por: usuario_id}, synchronize_session=False)
    db.session.commit()
    if not marcado:
        raise CorreoNoEnviado("Este paquete ya se envió.")
    try:
        enviador.enviar(mensaje)
    except Exception:
        db.session.query(Paquete).filter(Paquete.id == paquete.id).update(
            {Paquete.enviado_en: None, Paquete.enviado_por: None}, synchronize_session=False)
        db.session.commit()
        raise
    finally:
        db.session.refresh(paquete)
    log.info("Correo enviado", extra={"evento": "expedientes.correo_enviado", "datos": {
        "paquete": paquete.id, "llamada": paquete.call_id, "para": paquete.para, "cc": paquete.cc,
        "adjuntos": [a.nombre for a in adjuntos]}})
    return None


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def purgar_antiguos() -> int:
    """Borra los archivos de paquetes vencidos. El registro en la base se conserva."""
    limite = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=configuracion.retencion_dias())
    borrados = 0
    for paquete in Paquete.query.filter(Paquete.creado_en < limite):
        carpeta = carpeta_paquete(paquete.id)
        if carpeta.exists():
            shutil.rmtree(carpeta, ignore_errors=True)
            borrados += 1
    return borrados
