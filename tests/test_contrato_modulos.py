"""Contrato que cumple TODO módulo, sin que nadie escriba sus pruebas.

Se recorren todas las rutas que cada módulo registra (pantallas, API y estáticos) y se verifica
que el núcleo las proteja: sin sesión no entra nadie, sin el módulo asignado da 403 y con el
módulo deshabilitado da 503 aunque la persona lo tenga asignado. Un módulo nuevo queda cubierto
desde el primer push, sin agregar nada aquí.

Todas las respuestas esperadas las da el núcleo **antes** de ejecutar la vista: por eso estas
pruebas nunca llegan a conectarse a SAP, al buzón ni a otra cosa externa del módulo.
"""
import re

from app.core.models import Modulo
from app.core.registro import registro
from app.extensions import db

from .conftest import crear_usuario

# Valor de relleno por tipo de parámetro de la ruta: <int:id> → 1, <path:archivo> → "x/x"…
_RELLENO = {"int": "1", "float": "1.0", "path": "x/x", "uuid": "00000000-0000-0000-0000-000000000000"}
_PARAMETRO = re.compile(r"<(?:(\w+)(?:\([^)]*\))?:)?(\w+)>")


def _url(regla: str) -> str:
    return _PARAMETRO.sub(lambda m: _RELLENO.get(m.group(1) or "", "x"), regla)


def _rutas_de_modulos(app):
    """(módulo, método, URL) de cada ruta que pertenece a un módulo, incluidos sus Blueprints anidados."""
    ids = {d.id for d in registro(app).todos()}
    rutas = []
    for regla in app.url_map.iter_rules():
        modulo = regla.endpoint.split(".")[0]
        if modulo not in ids:
            continue
        metodo = "GET" if "GET" in regla.methods else sorted(regla.methods - {"HEAD", "OPTIONS"})[0]
        rutas.append((modulo, metodo, _url(regla.rule)))
    return rutas


def _pedir(cliente, metodo, url):
    return cliente.open(url, method=metodo)


def test_hay_modulos_y_rutas_que_revisar(app):
    # Si el descubrimiento dejara de encontrar módulos, las demás pruebas pasarían sin revisar nada.
    rutas = _rutas_de_modulos(app)
    assert {m for m, _, _ in rutas} == {d.id for d in registro(app).todos()}


def test_ninguna_ruta_de_un_modulo_responde_sin_sesion(app, client):
    abiertas = [(m, metodo, url, r.status_code) for m, metodo, url in _rutas_de_modulos(app)
                if (r := _pedir(client, metodo, url)).status_code not in (302, 401)]
    assert not abiertas, "Rutas de módulo que responden sin iniciar sesión: " + repr(abiertas)


def test_ninguna_ruta_de_un_modulo_responde_sin_tenerlo_asignado(app, entrar_como):
    # Un administrador tampoco entra a un módulo que no tiene asignado.
    for rol in ("usuario", "admin"):
        c = entrar_como(crear_usuario(f"sin_modulos_{rol}", rol=rol))
        abiertas = [(m, metodo, url, r.status_code) for m, metodo, url in _rutas_de_modulos(app)
                    if (r := _pedir(c, metodo, url)).status_code != 403]
        assert not abiertas, f"Rutas de módulo que no dan 403 a un {rol} sin el módulo: {abiertas!r}"
        c.post("/salir")


def test_un_modulo_deshabilitado_no_responde_ni_a_quien_lo_tiene_asignado(app, entrar_como):
    ids = [d.id for d in registro(app).todos()]
    c = entrar_como(crear_usuario("con_todos", modulos=ids))
    for fila in Modulo.query.filter(Modulo.id.in_(ids)):
        fila.activo = False
    db.session.commit()
    abiertas = [(m, metodo, url, r.status_code) for m, metodo, url in _rutas_de_modulos(app)
                if (r := _pedir(c, metodo, url)).status_code != 503]
    assert not abiertas, "Rutas de módulo deshabilitado que no dan 503: " + repr(abiertas)


def test_tener_modulos_asignados_no_abre_la_administracion(app, entrar_como):
    c = entrar_como(crear_usuario("operador_con_todo", modulos=[d.id for d in registro(app).todos()]))
    assert c.get("/admin/usuarios").status_code == 403
