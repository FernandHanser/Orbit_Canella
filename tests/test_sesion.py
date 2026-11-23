"""Expiración de la sesión (app/core/sesion.py): inactividad, jornada, motivo, aviso y formulario vencido."""
import time

from app import create_app
from app.core.sesion import CLAVE_INICIO, CLAVE_ULTIMA
from app.extensions import db

from .conftest import aislar_peticiones


def _mover(client, **segundos_atras):
    """Simula el paso del tiempo corriendo hacia atrás las marcas de la sesión."""
    with client.session_transaction() as s:
        for clave, atras in segundos_atras.items():
            s[clave] = s[clave] - atras


def test_inactividad_cierra_con_motivo_y_vuelve_a_la_pagina(app, entrar_como, autorizado):
    c = entrar_como(autorizado)
    assert c.get("/m/ejemplo/").status_code == 200
    _mover(c, **{CLAVE_ULTIMA: 61 * 60})
    r = c.get("/m/ejemplo/")
    assert r.status_code == 302 and "motivo=inactividad" in r.location and "siguiente=/m/ejemplo/" in r.location
    assert c.get("/m/ejemplo/").status_code == 302                     # ya no hay sesión
    assert "Tu sesión se cerró por inactividad" in c.get(r.location).get_data(as_text=True)


def test_la_actividad_renueva_y_la_jornada_no(app, entrar_como, autorizado):
    c = entrar_como(autorizado)
    _mover(c, **{CLAVE_ULTIMA: 50 * 60})
    assert c.get("/").status_code == 200                                # 50 min: sigue y se renueva
    _mover(c, **{CLAVE_ULTIMA: 50 * 60})
    assert c.get("/").status_code == 200                                # otros 50: sigue (renovada)
    _mover(c, **{CLAVE_INICIO: 10 * 3600 + 1})
    r = c.get("/")
    assert r.status_code == 302 and "motivo=jornada" in r.location


def test_consultar_estado_no_cuenta_como_actividad(app, entrar_como, autorizado):
    c = entrar_como(autorizado)
    _mover(c, **{CLAVE_ULTIMA: 59 * 60})
    estado = c.get("/sesion/estado").get_json()
    assert estado["motivo"] == "inactividad" and 0 < estado["segundos"] <= 60
    _mover(c, **{CLAVE_ULTIMA: 2 * 60})                                 # si el estado hubiera renovado, seguiría viva
    assert c.get("/").status_code == 302


def test_extender_renueva_la_inactividad(app, entrar_como, autorizado):
    c = entrar_como(autorizado)
    _mover(c, **{CLAVE_ULTIMA: 59 * 60})
    datos = c.post("/sesion/extender").get_json()
    assert datos["inactividad"] > 59 * 60
    _mover(c, **{CLAVE_ULTIMA: 30 * 60})
    assert c.get("/").status_code == 200


def test_api_con_sesion_vencida_responde_401(app, entrar_como, autorizado):
    c = entrar_como(autorizado)
    _mover(c, **{CLAVE_ULTIMA: 2 * 3600})
    r = c.get("/m/ejemplo/api/estado")
    assert r.status_code == 401 and r.get_json()["error"] == "sesion_vencida"


def test_pagina_con_sesion_trae_el_aviso(app, entrar_como, autorizado):
    html = entrar_como(autorizado).get("/").get_data(as_text=True)
    assert 'data-sesion-segundos="' in html and 'id="modal-sesion"' in html and "js/sesion.js" in html
    assert "Extender sesión" in html


def test_login_sin_motivo_no_muestra_aviso(client):
    assert "clock-exclamation" not in client.get("/acceso").get_data(as_text=True)


def test_formulario_con_sesion_vencida_lleva_al_login_y_no_a_un_400(tmp_path):
    """Con CSRF activo (como en producción), un formulario enviado sin sesión daba 400 Bad Request."""
    app = create_app("testing", LOG_DIR=str(tmp_path / "logs"), WTF_CSRF_ENABLED=True)
    aislar_peticiones(app)
    with app.app_context():
        db.create_all()
        r = app.test_client().post("/m/ejemplo/ejecutar", data={"pasos": "1", "csrf_token": "de-una-sesion-vencida"})
        assert r.status_code == 302 and "motivo=formulario" in r.location
        db.session.remove()
        db.drop_all()


def test_sesiones_abiertas_antes_del_control_no_se_cierran(app, entrar_como, autorizado):
    c = entrar_como(autorizado)
    with c.session_transaction() as s:
        s.pop(CLAVE_INICIO)
        s.pop(CLAVE_ULTIMA)
    assert c.get("/").status_code == 200
    with c.session_transaction() as s:
        assert abs(s[CLAVE_INICIO] - time.time()) < 5
