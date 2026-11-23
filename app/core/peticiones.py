"""Utilidades sobre la petición HTTP actual, compartidas por autenticación y autorización."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import request


def es_peticion_api() -> bool:
    ruta = request.path
    return "/api/" in ruta or ruta.endswith("/api") or request.is_json or (
        request.accept_mimetypes.best == "application/json"
    )


def es_url_segura(destino: str | None) -> bool:
    """Evita redirecciones abiertas: solo rutas relativas del propio sitio."""
    if not destino:
        return False
    destino = destino.strip()
    if not destino.startswith("/") or destino.startswith("//") or destino.startswith("/\\"):
        return False
    partes = urlparse(destino)
    return not partes.scheme and not partes.netloc
