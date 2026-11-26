"""Fixtures comunes. STOD se reemplaza por ``ProveedorSimulado`` (AUTH_PROVEEDOR=simulado en
el ambiente testing): las pruebas nunca se conectan a la base real."""
from contextlib import contextmanager

import pytest
from flask import g
from sqlalchemy import event

from app import create_app
from app.core.catalogo import sincronizar_catalogo
from app.core.identidad import proveedor_identidad
from app.core.models import PermisoModulo, Usuario
from app.extensions import db


@contextmanager
def contar_consultas():
    """Cuenta las sentencias SQL ejecutadas dentro del bloque (detectar N+1 en una prueba:
    con `with contar_consultas() as n:`, `n[0]` debe quedar fijo sin importar cuántas filas)."""
    conteo = [0]

    def _contar(*_a, **_kw):
        conteo[0] += 1

    event.listen(db.engine, "before_cursor_execute", _contar)
    try:
        yield conteo
    finally:
        event.remove(db.engine, "before_cursor_execute", _contar)

CONTRASENA = "Clave-Stod-2026"


# Las pruebas de punta a punta (tests/e2e, Playwright) abren un navegador real: tardan más y
# necesitan requirements-e2e.txt. Por eso no corren en `python -m pytest` ni en GitHub Actions;
# se piden con `python -m pytest --e2e tests/e2e`. Ver docs/PRUEBAS.md.
def pytest_addoption(parser):
    parser.addoption("--e2e", action="store_true", help="Corre también las pruebas de punta a punta (tests/e2e).")


def pytest_ignore_collect(collection_path, config):
    if collection_path.name == "e2e" and not config.getoption("--e2e"):
        return True
    return None


def aislar_peticiones(app):
    """Las pruebas mantienen un app_context abierto para usar la base de datos, y Flask
    reutiliza ese contexto (y su ``g``) en cada petición del cliente de pruebas. Se limpia
    ``g`` al terminar cada petición para que el usuario cargado por Flask-Login o el token
    CSRF de un cliente no se filtren al siguiente, como ocurre en producción."""

    @app.teardown_request
    def _limpiar_g(_exc):
        for clave in list(g):
            g.pop(clave, None)


@pytest.fixture
def app(tmp_path):
    app = create_app("testing", LOG_DIR=str(tmp_path / "logs"))
    aislar_peticiones(app)
    with app.app_context():
        db.create_all()
        sincronizar_catalogo()
        yield app
        db.session.remove()
        db.drop_all()


def stod():
    """El STOD simulado de la aplicación en curso."""
    return proveedor_identidad()


def crear_usuario(usuario, rol=Usuario.ROL_USUARIO, modulos=(), activo=True, activo_stod=True, en_hub=True):
    """Registra el usuario en el STOD simulado y, si ``en_hub``, también en el hub."""
    identidad = stod().registrar(usuario, CONTRASENA, email=f"{usuario}@canella.test", activo=activo_stod)
    if not en_hub:
        return identidad
    u = Usuario(usuario_stod=usuario.lower(), stod_user_id=identidad.user_id, nombre=identidad.nombre_visible,
                email=identidad.email, rol=rol, activo=activo)
    for m in modulos:
        u.permisos.append(PermisoModulo(modulo_id=m))
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def superadmin(app):
    return crear_usuario("superadmin", rol=Usuario.ROL_SUPERADMIN)


@pytest.fixture
def admin(app):
    return crear_usuario("admin1", rol=Usuario.ROL_ADMIN)


@pytest.fixture
def autorizado(app):
    return crear_usuario("autorizado", modulos=["ejemplo"])


@pytest.fixture
def sin_permiso(app):
    return crear_usuario("sinpermiso")


@pytest.fixture
def client(app):
    return app.test_client()


def entrar(client, usuario, contrasena=CONTRASENA, **kw):
    return client.post("/acceso", data={"usuario": usuario, "contrasena": contrasena}, **kw)


@pytest.fixture
def entrar_como(client):
    def _entrar(usuario):
        r = entrar(client, usuario.usuario_stod)
        assert r.status_code == 302, r.data
        return client

    return _entrar
