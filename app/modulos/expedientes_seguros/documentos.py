"""Operaciones sobre PDF, todas en el servidor (la ficha prohíbe servicios públicos para PDF).

* Miniaturas con pypdfium2 (Chromium PDFium): rápidas con escaneos de la Canon (~20 ms/página).
* Armado del paquete con pypdf: copia las páginas elegidas a un PDF nuevo. **El original de SAP
  nunca se modifica**: solo se lee.

Import diferido de las bibliotecas: se instalan con requirements-expedientes_seguros.txt y el
hub debe poder cargar el módulo sin ellas.
"""
from __future__ import annotations

import hashlib
import io
import threading
from pathlib import Path
from typing import Sequence

ANCHO_MINIATURA = 180
ANCHO_AMPLIADA = 1400   # legible: se revisa cada documento antes de asignarlo


# PDFium no es seguro con hilos: el servidor atiende varias miniaturas a la vez y dos renders
# simultáneos pueden salir en blanco (pasó el 28/09/2026 con la llamada 51595). Se serializan.
_PDFIUM = threading.Lock()


class PdfInvalido(ValueError):
    """El archivo no es un PDF legible."""


def leer(ruta: str | Path) -> bytes:
    try:
        return Path(ruta).read_bytes()
    except OSError as exc:
        raise FileNotFoundError(f"No se pudo leer el expediente en {ruta}: {exc.strerror or exc}") from exc


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def contar_paginas(datos: bytes) -> int:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        return len(PdfReader(io.BytesIO(datos)).pages)
    except (PdfReadError, ValueError, KeyError) as exc:
        raise PdfInvalido("El archivo no es un PDF válido.") from exc


def imagen_pagina(datos: bytes, pagina: int, ancho: int = ANCHO_MINIATURA) -> bytes:
    """JPEG de una página (1-based) con el ancho indicado."""
    import pypdfium2 as pdfium

    with _PDFIUM:
        documento = pdfium.PdfDocument(datos)
        try:
            if not 1 <= pagina <= len(documento):
                raise IndexError(f"La página {pagina} no existe.")
            hoja = documento[pagina - 1]
            imagen = hoja.render(scale=ancho / hoja.get_width()).to_pil().convert("RGB")
        finally:
            documento.close()
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", quality=72, optimize=True)
    return salida.getvalue()


def armar(datos: bytes, paginas: Sequence[int], anteponer: bytes | None = None) -> bytes:
    """PDF nuevo con las ``paginas`` (1-based, en ese orden) del original. Con ``anteponer``
    (la factura, cuando va unida), sus páginas van primero."""
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter()
    if anteponer:
        for hoja in PdfReader(io.BytesIO(anteponer)).pages:
            escritor.add_page(hoja)
    lector = PdfReader(io.BytesIO(datos))
    total = len(lector.pages)
    for numero in paginas:
        if not 1 <= numero <= total:
            raise IndexError(f"La página {numero} no existe (el expediente tiene {total}).")
        escritor.add_page(lector.pages[numero - 1])
    escritor.add_metadata({"/Producer": "ORBIT Canella", "/Creator": "Expedientes de Seguros (Taller)"})
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def concatenar(piezas: Sequence[bytes]) -> bytes:
    """Un PDF con todas las páginas de cada pieza de ``piezas``, en orden (ninguna se modifica).
    Generaliza el ``anteponer`` de ``armar`` a más de dos documentos: así se junta en un solo
    archivo lo que viene de distintos anexos de la llamada (expediente, DPI a color...)."""
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter()
    for pieza in piezas:
        for hoja in PdfReader(io.BytesIO(pieza)).pages:
            escritor.add_page(hoja)
    escritor.add_metadata({"/Producer": "ORBIT Canella", "/Creator": "Expedientes de Seguros (Taller)"})
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()
