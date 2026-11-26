"""Servidor de QA: el hub real con base SQLite temporal, STOD simulado y usuarios sembrados.

Lo usan las pruebas de punta a punta (``tests/e2e``) y sirve para revisar pantallas a mano o con
el skill ``qa-orbit``, sin tocar la base real::

    python -m tests.e2e.servidor                 # http://127.0.0.1:5057
    python -m tests.e2e.servidor --puerto 0      # el primer puerto libre (lo imprime)

**Nada del .env llega aquí.** ``app/config.py`` carga el ``.env`` al importarse; este archivo
borra después del entorno todas las variables que vienen de ese archivo (STOD, SAP, Exchange,
SMTP, carpetas, DATABASE_URL). Así ningún módulo puede conectarse a un sistema real aunque la
pantalla lo intente: falla con «falta configuración», que es lo que se quiere ver en QA.
"""
from __future__ import annotations

import argparse
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from app import create_app
from app.config import BASE_DIR

CONTRASENA = "Clave-QA-2026"


def _olvidar_env_real() -> None:
    for clave in dotenv_values(BASE_DIR / ".env"):
        os.environ.pop(clave, None)


@dataclass(frozen=True)
class UsuarioQA:
    usuario: str
    rol: str
    con_modulos: bool
    nombres: str
    descripcion: str


USUARIOS = (
    UsuarioQA("qa_super", "superadmin", True, "Sara", "Superadministrador con todos los módulos"),
    UsuarioQA("qa_admin", "admin", False, "Adán", "Administrador sin módulos asignados"),
    UsuarioQA("qa_operador", "usuario", True, "Olga", "Operador con todos los módulos"),
    UsuarioQA("qa_sin_modulos", "usuario", False, "Simón", "Operador sin módulos (debe ver 403 en cada módulo)"),
)


def crear_app_qa(carpeta: Path | None = None, **overrides):
    """App ``testing`` con base en archivo (la comparten los hilos del servidor) y usuarios QA."""
    _olvidar_env_real()
    carpeta = Path(carpeta or tempfile.mkdtemp(prefix="orbit-qa-"))
    config = {
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(carpeta / 'qa.db').as_posix()}",
        "LOG_DIR": str(carpeta / "logs"),
        "WTF_CSRF_ENABLED": True,          # como en producción: el JS debe mandar el token
        "SESSION_COOKIE_SECURE": False,    # HTTP local
        **overrides,
    }
    app = create_app("testing", **config)
    app.instance_path = str(carpeta / "instance")
    with app.app_context():
        _sembrar(app)
    return app


def _sembrar(app) -> None:
    from app.core.catalogo import sincronizar_catalogo
    from app.core.identidad import proveedor_identidad
    from app.core.models import PermisoModulo, Usuario
    from app.core.registro import registro
    from app.extensions import db

    # Siempre desde cero: si la carpeta se reutiliza, los datos de una corrida anterior no deben
    # cambiar lo que se ve en esta.
    db.drop_all()
    db.create_all()
    sincronizar_catalogo()
    ids = [d.id for d in registro(app).todos()]
    for u in USUARIOS:
        identidad = proveedor_identidad().registrar(u.usuario, CONTRASENA, email=f"{u.usuario}@canella.test")
        # Con nombres y apellidos, como una persona ya registrada: el formulario de usuario los
        # exige, y sin ellos la administración muestra «Sin nombre registrado» en todas las filas.
        fila = Usuario(usuario_stod=u.usuario, stod_user_id=identidad.user_id, nombre=f"{u.nombres} QA",
                       nombres=u.nombres, apellidos="QA", email=identidad.email, rol=u.rol, activo=True)
        if u.con_modulos:
            fila.permisos.extend(PermisoModulo(modulo_id=m) for m in ids)
        db.session.add(fila)
    db.session.commit()


class ServidorQA:
    """Servidor WSGI en un hilo. ``url`` queda lista al iniciar; ``detener()`` lo apaga."""

    def __init__(self, app, puerto: int = 5057, host: str = "127.0.0.1"):
        from werkzeug.serving import make_server

        self.app = app
        self._srv = make_server(host, puerto, app, threaded=True)
        self.url = f"http://{host}:{self._srv.server_port}"
        self._hilo = threading.Thread(target=self._srv.serve_forever, daemon=True)

    def iniciar(self) -> "ServidorQA":
        self._hilo.start()
        return self

    def detener(self) -> None:
        self._srv.shutdown()
        self._hilo.join(timeout=5)


def main() -> None:
    p = argparse.ArgumentParser(description="Servidor de QA de ORBIT (SQLite temporal, STOD simulado).")
    p.add_argument("--puerto", type=int, default=5057, help="0 = el primer puerto libre")
    args = p.parse_args()
    if args.puerto == 5000:
        raise SystemExit("El 5000 es el del servidor de desarrollo con la base real: usa otro.")
    servidor = ServidorQA(crear_app_qa(), args.puerto)
    print(f"ORBIT QA en {servidor.url}  (Ctrl+C para detener)")
    print(f"Contraseña de todos los usuarios: {CONTRASENA}")
    for u in USUARIOS:
        print(f"  {u.usuario:<16} {u.nombres + ' QA':<10} {u.descripcion}")
    try:
        servidor._srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
