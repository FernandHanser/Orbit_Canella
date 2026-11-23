"""Escritura de los archivos en la carpeta compartida, idempotente.

Si una corrida se corta después de guardar un archivo pero antes de mover el correo, la
siguiente vuelve a procesarlo. El archivador reconoce el archivo por su contenido (SHA-256) y no
lo duplica. Un archivo distinto con el mismo nombre (una corrección) se guarda como
``nombre (1).pdf``, igual que en el prototipo.

La cuenta de servicio que ejecuta la tarea necesita permiso de escritura sobre la carpeta: el
módulo no usa ``net use`` ni guarda contraseñas de red.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence


@dataclass(frozen=True)
class ArchivoGuardado:
    carpeta: str          # relativa a la raíz, con "/"
    nombre: str           # nombre final en la carpeta
    sha256: str
    duplicado: bool       # ya existía con el mismo contenido: no se escribió de nuevo


def sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _candidatos(nombre: str) -> Iterator[str]:
    base, ext = os.path.splitext(nombre)
    yield nombre
    contador = 1
    while True:
        yield f"{base} ({contador}){ext}"
        contador += 1


def _sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


class Archivador:
    def __init__(self, raiz: str | Path) -> None:
        self.raiz = Path(raiz)

    def carpeta(self, partes: Sequence[str]) -> Path:
        destino = self.raiz.joinpath(*partes)
        # Las partes vienen de la tabla de empresas y de la fecha, pero se verifica igual.
        if not destino.resolve().is_relative_to(self.raiz.resolve()):
            raise ValueError(f"Carpeta de destino fuera de la raíz: {'/'.join(partes)}")
        return destino

    def guardar(self, partes: Sequence[str], nombre: str, contenido: bytes) -> ArchivoGuardado:
        """``nombre`` ya debe venir saneado (``reglas.nombre_seguro``)."""
        destino = self.carpeta(partes)
        destino.mkdir(parents=True, exist_ok=True)
        huella = sha256(contenido)
        carpeta = "/".join(partes)
        for candidato in _candidatos(nombre):
            ruta = destino / candidato
            if not ruta.exists():
                self._escribir(ruta, contenido)
                return ArchivoGuardado(carpeta, candidato, huella, duplicado=False)
            if _sha256_archivo(ruta) == huella:
                return ArchivoGuardado(carpeta, candidato, huella, duplicado=True)
        raise AssertionError("inalcanzable")

    @staticmethod
    def _escribir(ruta: Path, contenido: bytes) -> None:
        """Escribe en un temporal y lo renombra: un corte a mitad nunca deja un archivo truncado
        con el nombre final. ``os.rename`` en Windows falla si el destino ya existe (no pisa)."""
        temporal = ruta.with_name(f"~corte_caja_{uuid.uuid4().hex}.tmp")
        try:
            temporal.write_bytes(contenido)
            os.rename(temporal, ruta)
        finally:
            temporal.unlink(missing_ok=True)
