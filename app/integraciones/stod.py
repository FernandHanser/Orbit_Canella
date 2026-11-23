"""Conexión a STOD (SQL Server) e identidad de usuarios.

STOD guarda sus usuarios con ASP.NET Membership (tablas ``aspnet_Users`` y
``aspnet_Membership`` en ``STOD_SAPBONE``). El hub los usa para iniciar sesión, igual que
CODA_REPORTS: un usuario puede entrar si ``IsApproved = 1`` e ``IsLockedOut = 0`` y su
contraseña coincide con el hash guardado. El hub **solo lee** estas tablas.

Formato del hash (``PasswordFormat = 1``)::

    base64( SHA1( base64decode(PasswordSalt) + contraseña.encode("utf-16le") ) ) == Password

Implementa el contrato ``ProveedorIdentidad`` de ``app/core/identidad.py`` y se registra al
crear la aplicación (``instalar``). El núcleo no importa este archivo.

La conexión (``conexion_stod()``) también la usan los módulos que consultan STOD.

En el ambiente ``testing`` se usa ``ProveedorSimulado`` para no depender de la base real.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

from flask import Flask, current_app

from app.core.identidad import Identidad, IdentidadNoDisponible, normalizar_usuario, registrar_proveedor
from app.core.logs import get_logger

if TYPE_CHECKING:  # pyodbc se importa al conectar, no al iniciar el hub
    import pyodbc

log = get_logger("core")

FORMATO_HASH = 1  # ASP.NET Membership: 0 = texto plano, 1 = hash, 2 = cifrado

_SQL_USUARIO = """
    SELECT u.UserId, u.UserName, m.Email, m.IsApproved, m.IsLockedOut,
           m.Password, m.PasswordSalt, m.PasswordFormat
    FROM aspnet_Users u
    INNER JOIN aspnet_Membership m ON m.UserId = u.UserId
    WHERE u.LoweredUserName = ?
"""


class StodNoDisponible(IdentidadNoDisponible):
    """No se pudo consultar STOD (red, credenciales del hub o servidor caído)."""


def verificar_hash_membership(contrasena: str, hash_guardado: str, salt: str) -> bool:
    try:
        calculado = hashlib.sha1(base64.b64decode(salt) + contrasena.encode("utf-16le")).digest()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(base64.b64encode(calculado).decode("ascii"), hash_guardado or "")


# ---------------------------------------------------------------------------- conexión

def _cadena_conexion(cfg) -> str:
    faltantes = [k for k in ("STOD_SERVER", "STOD_DATABASE", "STOD_USERNAME", "STOD_PASSWORD") if not cfg.get(k)]
    if faltantes:
        raise StodNoDisponible(f"Falta configurar: {', '.join(faltantes)}")
    return (
        f"DRIVER={{{cfg['STOD_ODBC_DRIVER']}}};SERVER={cfg['STOD_SERVER']};DATABASE={cfg['STOD_DATABASE']};"
        f"UID={cfg['STOD_USERNAME']};PWD={cfg['STOD_PASSWORD']};TrustServerCertificate=yes;"
    )


@contextmanager
def conexion_stod() -> Iterator["pyodbc.Connection"]:
    """Conexión a STOD con la configuración ``STOD_*``. Lanza ``StodNoDisponible`` si falla."""
    import pyodbc

    cfg = current_app.config
    try:
        conn = pyodbc.connect(_cadena_conexion(cfg), timeout=cfg["STOD_TIMEOUT"])
    except pyodbc.Error as exc:
        # El mensaje de pyodbc no incluye la contraseña, pero se resume para no llenar el log.
        raise StodNoDisponible(f"No se pudo conectar a STOD: {type(exc).__name__}") from exc
    try:
        yield conn
    finally:
        try:
            conn.close()
        except pyodbc.Error:
            pass


# ---------------------------------------------------------------------------- proveedores

class ProveedorStod:
    """Identidad contra las tablas de ASP.NET Membership de STOD (solo lectura)."""

    # Hash con salt aleatorio para igualar el tiempo de respuesta si el usuario no existe.
    _SALT_FICTICIO = base64.b64encode(secrets.token_bytes(16)).decode("ascii")

    def _fila(self, usuario: str):
        import pyodbc

        try:
            with conexion_stod() as conn:
                cursor = conn.cursor()
                cursor.execute(_SQL_USUARIO, normalizar_usuario(usuario))
                return cursor.fetchone()
        except pyodbc.Error as exc:
            raise StodNoDisponible(f"Error al consultar STOD: {type(exc).__name__}") from exc

    @staticmethod
    def _identidad(fila) -> Identidad:
        return Identidad(
            user_id=str(fila.UserId),
            usuario=fila.UserName,
            email=(fila.Email or "").strip().lower() or None,
            activo=bool(fila.IsApproved) and not bool(fila.IsLockedOut),
        )

    def autenticar(self, usuario: str, contrasena: str) -> Identidad | None:
        """Identidad si la contraseña es correcta (activa o no); None si no coincide."""
        fila = self._fila(usuario)
        if fila is None:
            verificar_hash_membership(contrasena, "", self._SALT_FICTICIO)
            return None
        if fila.PasswordFormat != FORMATO_HASH:
            log.warning(
                "Usuario STOD con formato de contraseña no soportado",
                extra={"evento": "auth.stod_formato", "datos": {"usuario_stod": fila.UserName, "formato": fila.PasswordFormat}},
            )
            return None
        if not verificar_hash_membership(contrasena, fila.Password, fila.PasswordSalt):
            return None
        return self._identidad(fila)

    def consultar(self, usuario: str) -> Identidad | None:
        """Estado actual del usuario en STOD, sin contraseña; None si no existe."""
        fila = self._fila(usuario)
        return self._identidad(fila) if fila is not None else None


class ProveedorSimulado:
    """Proveedor en memoria para pruebas automáticas. Solo se permite con TESTING."""

    def __init__(self) -> None:
        self.usuarios: dict[str, tuple[str, Identidad]] = {}
        self.disponible = True

    def registrar(self, usuario: str, contrasena: str, email: str | None = None, activo: bool = True) -> Identidad:
        identidad = Identidad(user_id=secrets.token_hex(8), usuario=usuario, email=email, activo=activo)
        self.usuarios[normalizar_usuario(usuario)] = (contrasena, identidad)
        return identidad

    def cambiar_estado(self, usuario: str, activo: bool) -> None:
        contrasena, identidad = self.usuarios[normalizar_usuario(usuario)]
        self.usuarios[normalizar_usuario(usuario)] = (
            contrasena, Identidad(identidad.user_id, identidad.usuario, identidad.email, activo)
        )

    def _verificar_disponible(self) -> None:
        if not self.disponible:
            raise StodNoDisponible("STOD simulado no disponible")

    def autenticar(self, usuario: str, contrasena: str) -> Identidad | None:
        self._verificar_disponible()
        registro = self.usuarios.get(normalizar_usuario(usuario))
        if registro is None or not hmac.compare_digest(registro[0], contrasena):
            return None
        return registro[1]

    def consultar(self, usuario: str) -> Identidad | None:
        self._verificar_disponible()
        registro = self.usuarios.get(normalizar_usuario(usuario))
        return registro[1] if registro else None


def instalar(app: Flask) -> None:
    tipo = app.config.get("AUTH_PROVEEDOR", "stod")
    if tipo == "simulado":
        if not app.config.get("TESTING"):
            raise RuntimeError("AUTH_PROVEEDOR=simulado solo se permite en el ambiente de pruebas.")
        registrar_proveedor(app, ProveedorSimulado())
    elif tipo == "stod":
        registrar_proveedor(app, ProveedorStod())
    else:
        raise RuntimeError(f"AUTH_PROVEEDOR desconocido: {tipo!r}")
