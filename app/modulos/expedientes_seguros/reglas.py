"""Reglas puras del paquete: nombres de archivo, selección de páginas, plantilla y correo.

Formato real de Caja (correos de ejemplo en contexto/): asunto
``<ASEGURADORA>//Serie: <serie> Número: <número>//CANELLA`` y cuerpo "Adjunto documentos y factura
Serie: … Número: …". Los adjuntos se nombraban ``DOC <llamada>.pdf`` y ``FAC <llamada>-<aseguradora>.pdf``;
ahora el paquete se llama ``<llamada>_<aseguradora>_<AAAA-MM-DD>.pdf`` (decisión del 28/09/2026).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from email.utils import formatdate, getaddresses, make_msgid, parseaddr
from typing import Mapping, Sequence

VARIABLES = ("aseguradora", "serie", "numero", "reclamo", "poliza", "llamada", "orden")
_VARIABLE = re.compile(r"\{(" + "|".join(VARIABLES) + r")\}")
_INVALIDOS_ARCHIVO = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass(frozen=True)
class Adjunto:
    nombre: str
    contenido: bytes


def _limpio(texto: str) -> str:
    return " ".join(_INVALIDOS_ARCHIVO.sub("", texto).split()).strip(" .")


def nombre_paquete(call_id: int, aseguradora: str, fecha: date) -> str:
    """``51595_ASEGURADORA LA CEIBA, S. A._2026-09-28.pdf`` (sin caracteres inválidos en Windows)."""
    return f"{call_id}_{_limpio(aseguradora) or 'SIN ASEGURADORA'}_{fecha.isoformat()}.pdf"


def nombre_factura(call_id: int, aseguradora: str) -> str:
    """La factura que Caja sube aparte (no viene de páginas de SAP): ``FAC 51595-ASEGURADORA LA
    CEIBA, S. A.pdf``. Distinto de ``nombre_documento_separado`` para no confundir el archivo que
    subió Caja con uno armado de páginas del expediente."""
    return f"FAC {call_id}-{_limpio(aseguradora) or 'SIN ASEGURADORA'}.pdf"


def nombre_documento_separado(call_id: int, aseguradora: str, documento: str) -> str:
    """Un documento del checklist marcado «archivo aparte», armado con sus páginas del expediente:
    ``Detalle de reparación 51595-ASEGURADORA LA CEIBA, S. A.pdf``. El nombre del documento va
    primero para que se identifique de un vistazo entre varios adjuntos."""
    return f"{_limpio(documento) or 'Documento'} {call_id}-{_limpio(aseguradora) or 'SIN ASEGURADORA'}.pdf"


def ruta_accesible(ruta: str, servidor: str) -> str:
    r"""Cambia el servidor de una ruta UNC: ``\\Srv-sapcanella\x\a.pdf`` → ``\\10.0.0.5\x\a.pdf``.
    Sin ``servidor``, o si la ruta no es UNC, la deja igual."""
    if not servidor or not ruta.startswith("\\\\"):
        return ruta
    resto = ruta[2:].split("\\", 1)
    return "\\\\" + servidor + ("\\" + resto[1] if len(resto) > 1 else "")


def es_factura(nombre: str) -> bool:
    """El documento «Factura original» del checklist lo cumple la factura que sube Caja."""
    return "factura original" in " ".join((nombre or "").lower().split())


def es_dpi(nombre: str) -> bool:
    """El DPI a color de la llamada: un segundo anexo en SAP (``ATC1``, misma carpeta), siempre PDF
    y con el nombre empezando en «DPI» (confirmado en ``ATC1`` real: no reemplaza el expediente,
    es un documento aparte que se combina con él, ver ``mapa_paginas``)."""
    return (nombre or "").strip().upper().startswith("DPI")


def mapa_paginas(bloques: Sequence[tuple[int, int]]) -> dict[int, tuple[int, int]]:
    """Expediente combinado de la llamada: numera en un solo consecutivo las páginas de varios
    anexos (``bloques``: línea de SAP → cantidad de páginas, en el orden en que se combinan — el
    expediente antes que el DPI). Resultado: {página combinada: (línea, página dentro de ese
    anexo)}; con esto el cajero elige páginas de todos los anexos como si fueran un solo documento,
    y al armar el paquete cada página se copia de su archivo de origen."""
    mapa: dict[int, tuple[int, int]] = {}
    n = 0
    for linea, cantidad in bloques:
        for local in range(1, cantidad + 1):
            n += 1
            mapa[n] = (linea, local)
    return mapa


def paginas_por_linea(paginas: Sequence[int], mapa: Mapping[int, tuple[int, int]]) -> dict[int, list[int]]:
    """De las páginas combinadas elegidas, cuáles le tocan a cada línea de anexo (su página dentro
    de ese anexo, en el mismo orden): para armar el PDF final tomando cada hoja de su archivo de
    origen (expediente, DPI...)."""
    resultado: dict[int, list[int]] = {}
    for pagina in paginas:
        linea, local = mapa[pagina]
        resultado.setdefault(linea, []).append(local)
    return resultado


def evaluar_checklist(documentos: Sequence[Mapping], asignaciones: Mapping[int, int], paginas: Sequence[int],
                      con_factura: bool) -> list[dict]:
    """Estado de cada documento con las páginas marcadas que lo contienen.

    ``documentos``: ``{"id", "nombre", "obligatorio"}``; ``asignaciones``: página → ids de documento
    (una página puede contener varios; también se acepta un solo id). Solo cuentan las páginas que
    van en el paquete."""
    elegidas = set(paginas)
    resultado = []
    for doc in documentos:
        suyas = sorted(p for p, d in asignaciones.items()
                       if p in elegidas and doc["id"] in (d if isinstance(d, (list, tuple, set)) else (d,)))
        factura = es_factura(doc["nombre"]) and con_factura
        resultado.append({
            "documento": doc["nombre"], "obligatorio": bool(doc["obligatorio"]),
            "paginas": rangos(suyas), "factura": factura, "presente": bool(suyas) or factura,
        })
    return resultado


def separar_por_documento(
    paginas: Sequence[int], asignaciones: Mapping[int, int], aparte: Mapping[int, str],
) -> tuple[list[int], dict[int, list[int]]]:
    """De las páginas elegidas, cuáles van al PDF principal y cuáles al archivo propio de cada
    documento marcado «aparte» (``aparte``: id de documento → su nombre, solo los que sí van
    aparte). Una página sin documento asignado, o con alguno que **no** va aparte, entra también
    al principal: una página puede repetirse en más de un archivo (son copias de sus páginas, no
    un recorte exclusivo; así una hoja con DPI y tarjeta puede ir completa en ambos documentos)."""
    principal: list[int] = []
    por_documento: dict[int, list[int]] = {}
    for pagina in paginas:
        ids = asignaciones.get(pagina, ())
        ids = ids if isinstance(ids, (list, tuple, set)) else (ids,)
        propios_aparte = [i for i in ids if i in aparte]
        if not ids or len(propios_aparte) < len(ids):
            principal.append(pagina)
        for doc_id in propios_aparte:
            por_documento.setdefault(doc_id, []).append(pagina)
    return principal, por_documento


def faltantes(checklist: Sequence[Mapping]) -> list[str]:
    return [d["documento"] for d in checklist if d["obligatorio"] and not d["presente"]]


def rangos(paginas: Sequence[int]) -> str:
    """``[1, 2, 3, 7, 9, 10]`` → ``"1-3, 7, 9-10"`` (para el registro y la pantalla)."""
    partes, ordenadas = [], sorted(set(paginas))
    i = 0
    while i < len(ordenadas):
        j = i
        while j + 1 < len(ordenadas) and ordenadas[j + 1] == ordenadas[j] + 1:
            j += 1
        partes.append(str(ordenadas[i]) if i == j else f"{ordenadas[i]}-{ordenadas[j]}")
        i = j + 1
    return ", ".join(partes)


def paginas_elegidas(valores: Sequence[str], total: int) -> list[int]:
    """Páginas marcadas en el formulario, sin repetir, dentro de 1..total y en orden."""
    elegidas = set()
    for valor in valores:
        if str(valor).isdigit() and 1 <= int(valor) <= total:
            elegidas.add(int(valor))
    return sorted(elegidas)


def aplicar_plantilla(plantilla: str, datos: Mapping[str, str]) -> str:
    """Reemplaza solo ``{aseguradora}``, ``{serie}``… (sin ``str.format``: nada de atributos)."""
    return _VARIABLE.sub(lambda m: str(datos.get(m.group(1), "")), plantilla or "")


def direcciones(texto: str) -> list[str]:
    """Correos de una lista separada por ``;`` o ``,`` (acepta ``Nombre <correo>``)."""
    return [correo.strip() for _, correo in getaddresses([(texto or "").replace(";", ",")]) if "@" in correo]


def correo_invalido(texto: str) -> str | None:
    """La primera dirección mal escrita de la lista, o ``None`` si todas son válidas.

    Se revisa cada elemento: ``getaddresses`` descarta en silencio lo que no entiende."""
    for elemento in re.split(r"[;,]", texto or ""):
        elemento = elemento.strip()
        if not elemento:
            continue
        _, correo = parseaddr(elemento)
        if not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", correo or ""):
            return elemento
    return None


def _mensaje(para: str, cc: str, asunto: str, cuerpo: str, adjuntos: Sequence[Adjunto]) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["To"] = ", ".join(direcciones(para))
    if direcciones(cc):
        mensaje["Cc"] = ", ".join(direcciones(cc))
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)
    for adjunto in adjuntos:
        mensaje.add_attachment(adjunto.contenido, maintype="application", subtype="pdf", filename=adjunto.nombre)
    return mensaje


def correo_eml(para: str, cc: str, asunto: str, cuerpo: str, adjuntos: Sequence[Adjunto]) -> bytes:
    """Borrador ``.eml``: Outlook lo abre como correo nuevo (``X-Unsent: 1``) desde la cuenta de
    quien lo abre, para revisarlo y enviarlo desde ahí (alternativa al envío desde el hub)."""
    mensaje = _mensaje(para, cc, asunto, cuerpo, adjuntos)
    mensaje["X-Unsent"] = "1"
    return bytes(mensaje)


def correo_saliente(remitente: str, para: str, cc: str, asunto: str, cuerpo: str,
                    adjuntos: Sequence[Adjunto], responder_a: str | None = None) -> EmailMessage:
    """El mismo correo, listo para enviarlo desde el buzón del hub. Las respuestas van a quien
    lo envió (``Reply-To``), no al buzón del robot."""
    mensaje = _mensaje(para, cc, asunto, cuerpo, adjuntos)
    mensaje["From"] = remitente
    if responder_a:
        mensaje["Reply-To"] = responder_a
    mensaje["Date"] = formatdate(localtime=True)
    mensaje["Message-ID"] = make_msgid(domain=remitente.rpartition("@")[2].strip("> ") or None)
    return mensaje
