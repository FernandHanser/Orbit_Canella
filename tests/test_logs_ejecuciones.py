"""Logs centrales identificados por módulo, ejecuciones y CLI."""
import logging
from datetime import timedelta
from pathlib import Path

from app.core.ejecuciones import ejecutar_tarea
from app.core.logs import buscar_logs, get_logger, sanear_datos, sanear_texto
from app.core.models import Ejecucion, Usuario
from app.core.registro import DefinicionModulo

from .conftest import CONTRASENA, entrar


def _eventos(app, **filtros):
    for h in logging.getLogger().handlers:
        h.flush()
    return buscar_logs(app.config["LOG_DIR"], **filtros)


def test_logs_distinguen_hub_y_modulos(app, entrar_como, autorizado):
    c = entrar_como(autorizado)
    c.post("/m/ejemplo/ejecutar", data={"pasos": "1"})
    get_logger("otro_modulo").info("Evento de otro módulo", extra={"evento": "prueba.otro"})

    core = _eventos(app, modulo="core")
    ejemplo = _eventos(app, modulo="ejemplo")
    otro = _eventos(app, modulo="otro_modulo")

    assert any(e["evento"] == "auth.acceso" and e["usuario"] == autorizado.usuario_stod for e in core)
    assert all(e["modulo"] == "core" for e in core)
    assert {"ejecucion.inicio", "demo.preparacion", "ejecucion.fin"} <= {e["evento"] for e in ejemplo}
    assert all(e["modulo"] == "ejemplo" for e in ejemplo)
    assert [e["evento"] for e in otro] == ["prueba.otro"]


def test_campos_minimos_de_cada_registro(app, entrar_como, autorizado):
    entrar_como(autorizado).post("/m/ejemplo/ejecutar", data={"pasos": "1"})
    for e in _eventos(app):
        assert {"ts", "nivel", "modulo", "evento", "mensaje", "usuario", "ejecucion_id"} <= e.keys()


def test_logs_filtrables_por_ejecucion(app, entrar_como, autorizado):
    c = entrar_como(autorizado)
    c.post("/m/ejemplo/ejecutar", data={"pasos": "1"})
    c.post("/m/ejemplo/ejecutar", data={"pasos": "2"})
    primera, segunda = Ejecucion.query.order_by(Ejecucion.inicio).all()
    ev1 = _eventos(app, ejecucion_id=primera.id)
    ev2 = _eventos(app, ejecucion_id=segunda.id)
    assert ev1 and ev2
    assert all(e["ejecucion_id"] == primera.id and e["usuario"] == autorizado.usuario_stod for e in ev1)
    assert len([e for e in ev2 if e["evento"] == "demo.paso"]) == 2


def test_error_registra_traza_y_estado(app, entrar_como, autorizado):
    entrar_como(autorizado).post("/m/ejemplo/ejecutar", data={"pasos": "1", "fallar": "1"})
    e = Ejecucion.query.one()
    assert e.estado == "error" and "Error simulado" in e.error
    errores = _eventos(app, ejecucion_id=e.id, nivel_minimo="ERROR")
    assert errores and "Traceback" in errores[0]["traza"]


def test_accesos_denegados_quedan_registrados(app, entrar_como, sin_permiso):
    entrar_como(sin_permiso).get("/m/ejemplo/")
    denegados = _eventos(app, modulo="ejemplo", nivel_minimo="WARNING")
    assert any(e["evento"] == "acceso.denegado" and e["usuario"] == sin_permiso.usuario_stod for e in denegados)


def test_no_se_registran_contrasenas(app, client, autorizado):
    entrar(client, autorizado.usuario_stod, "Clave-Secreta-Que-No-Debe-Aparecer")
    entrar(client, autorizado.usuario_stod)
    get_logger("core").info("token=abc123 password: xyz", extra={"datos": {"contrasena": "otra", "archivo": "a" * 5000}})
    for h in logging.getLogger().handlers:
        h.flush()
    contenido = "".join(p.read_text(encoding="utf-8") for p in Path(app.config["LOG_DIR"]).glob("*.jsonl"))
    for secreto in ("Clave-Secreta-Que-No-Debe-Aparecer", CONTRASENA, "abc123", "xyz", '"otra"'):
        assert secreto not in contenido
    assert "a" * 400 not in contenido  # textos largos se recortan


def test_saneamiento():
    assert sanear_texto("clave=1234 ok") == "clave=*** ok"
    assert sanear_datos({"api_key": "x", "n": 1, "lista": ["token: t"]}) == {"api_key": "***", "n": 1, "lista": ["token: ***"]}


def test_pantalla_de_logs_filtra_por_modulo(app, entrar_como, admin, autorizado):
    c_user = app.test_client()
    entrar(c_user, autorizado.usuario_stod)
    c_user.post("/m/ejemplo/ejecutar", data={"pasos": "1"})
    c = entrar_como(admin)
    html = c.get("/admin/logs?modulo=ejemplo").get_data(as_text=True)
    assert "demo.preparacion" in html and "auth.acceso" not in html
    e = Ejecucion.query.one()
    detalle = c.get(f"/admin/ejecuciones/{e.id}").get_data(as_text=True)
    assert "ejecucion.fin" in detalle and autorizado.usuario_stod in detalle


def test_tarea_sin_sesion_web(app):
    e = ejecutar_tarea("ejemplo", "demo", proceso="tarea-programada", parametros={"pasos": 0})
    assert e.estado == "advertencia" and e.usuario_id is None and e.iniciado_por == "proceso: tarea-programada"
    eventos = _eventos(app, ejecucion_id=e.id)
    assert eventos and all(ev["usuario"] == "proceso:tarea-programada" for ev in eventos)


def test_cli_tareas_y_superadmin(app):
    runner = app.test_cli_runner()
    r = runner.invoke(args=["tareas", "ejecutar", "ejemplo", "demo", "--proceso", "cron", "--param", "pasos=1"])
    assert r.exit_code == 0 and "exito" in r.output
    r = runner.invoke(args=["tareas", "ejecutar", "ejemplo", "demo", "--param", "fallar=1"])
    assert r.exit_code == 1

    r = runner.invoke(args=["usuarios", "superadmin", "FHanser"])
    assert r.exit_code == 0, r.output
    u = Usuario.query.filter_by(usuario_stod="fhanser").one()
    assert u.es_superadmin and u.pendiente_primer_ingreso
    r = runner.invoke(args=["usuarios", "quitar-superadmin", "fhanser"])
    assert r.exit_code != 0 and "al menos un superadministrador" in r.output
    assert "fhanser" in runner.invoke(args=["usuarios", "listar"]).output


def test_definicion_de_modulo_validada():
    from flask import Blueprint

    import pytest

    with pytest.raises(ValueError):
        DefinicionModulo(id="admin", nombre="x", descripcion="", icono="x", blueprint=Blueprint("admin", __name__))
    with pytest.raises(ValueError):
        DefinicionModulo(id="bueno", nombre="x", descripcion="", icono="x", blueprint=Blueprint("otro", __name__))
    d = DefinicionModulo(id="bueno", nombre="x", descripcion="", icono="x", blueprint=Blueprint("bueno", __name__))
    assert (d.ruta, d.permiso) == ("/m/bueno", "modulo.bueno")
    # Un módulo no puede montarse sobre rutas ajenas ni presentarse con el permiso de otro.
    for ajeno in ({"ruta": "/admin"}, {"ruta": "/m/corte_caja"}, {"permiso": "modulo.corte_caja"}):
        with pytest.raises(ValueError):
            DefinicionModulo(id="bueno", nombre="x", descripcion="", icono="x",
                             blueprint=Blueprint("bueno", __name__), **ajeno)


# ---------------------------------------------------------------- paginación

def test_paginacion_de_ejecuciones_conserva_filtros(app, entrar_como, admin):
    for _ in range(30):
        ejecutar_tarea("ejemplo", "demo", proceso="prueba", parametros={"pasos": 0})
    c = entrar_como(admin)
    p1 = c.get("/admin/ejecuciones?modulo=ejemplo").get_data(as_text=True)
    assert p1.count('href="/admin/ejecuciones/') == 15
    assert "Mostrando <span>1</span>–<span>15</span>" in p1 and "de <span>30</span>" in p1
    assert "modulo=ejemplo&amp;pagina=2" in p1
    p2 = c.get("/admin/ejecuciones?modulo=ejemplo&pagina=2").get_data(as_text=True)
    assert p2.count('href="/admin/ejecuciones/') == 15
    fuera = c.get("/admin/ejecuciones?pagina=99")
    assert fuera.status_code == 200


def test_paginacion_de_logs(app, entrar_como, admin):
    for i in range(60):
        get_logger("ejemplo").info("evento %s", i, extra={"evento": "prueba.pag"})
    c = entrar_como(admin)
    p1 = c.get("/admin/logs?texto=prueba.pag").get_data(as_text=True)
    assert p1.count("prueba.pag</td>") == 15 and "texto=prueba.pag&amp;pagina=2" in p1
    p4 = c.get("/admin/logs?texto=prueba.pag&pagina=4").get_data(as_text=True)
    assert p4.count("prueba.pag</td>") == 15 and "pagina=5" not in p4


def test_pagina_lista_limites():
    from app.core.paginacion import PaginaLista

    p = PaginaLista(list(range(51)), 9, 25)
    assert (p.page, p.pages, p.items, p.has_next, p.has_prev) == (3, 3, [50], False, True)
    vacia = PaginaLista([], 1, 25)
    assert (vacia.pages, vacia.items, vacia.has_next) == (1, [], False)


# ---------------------------------------------------------------- atomicidad

def test_ejecucion_fallida_revierte_los_cambios_de_la_tarea(app):
    """Lo que la tarea escribe en la base se confirma junto con su estado final, o se revierte."""
    import pytest

    from app.core.ejecuciones import ejecucion
    from app.extensions import db

    with pytest.raises(RuntimeError):
        with ejecucion("ejemplo", "atomicidad", proceso="prueba"):
            db.session.add(Usuario(usuario_stod="escrito_por_tarea", nombre="X", rol=Usuario.ROL_USUARIO, activo=True))
            db.session.flush()
            raise RuntimeError("falla a mitad de la tarea")

    assert Usuario.query.filter_by(usuario_stod="escrito_por_tarea").first() is None
    assert Ejecucion.query.one().estado == "error"

    with ejecucion("ejemplo", "atomicidad", proceso="prueba"):
        db.session.add(Usuario(usuario_stod="escrito_por_tarea", nombre="X", rol=Usuario.ROL_USUARIO, activo=True))
    db.session.rollback()  # nada pendiente: todo quedó confirmado con el estado "exito"
    assert Usuario.query.filter_by(usuario_stod="escrito_por_tarea").one()


def _ejecucion_en_curso(horas_atras: float, modulo_id: str = "ejemplo") -> str:
    from datetime import timedelta

    from app.core.models import ahora_utc
    from app.extensions import db

    fila = Ejecucion(modulo_id=modulo_id, tarea="demo", proceso="prueba", estado="en_curso",
                     inicio=ahora_utc() - timedelta(hours=horas_atras))
    db.session.add(fila)
    db.session.commit()
    return fila.id


def test_ejecuciones_colgadas_se_marcan_interrumpidas_al_iniciar(app):
    from app.core.ejecuciones import MENSAJE_INTERRUMPIDA, mantenimiento_al_iniciar
    from app.extensions import db

    app.config["EJECUCIONES_INTERRUMPIDAS_HORAS"] = 2
    vieja = _ejecucion_en_curso(horas_atras=3, modulo_id="modulo_a")
    reciente = _ejecucion_en_curso(horas_atras=0.5, modulo_id="modulo_b")  # corrida real de otro proceso
    terminada = ejecutar_tarea("ejemplo", "demo", proceso="prueba", parametros={"pasos": 1}).id

    mantenimiento_al_iniciar(app)

    v = db.session.get(Ejecucion, vieja)
    assert (v.estado, v.error) == ("interrumpida", MENSAJE_INTERRUMPIDA) and v.fin is not None
    assert db.session.get(Ejecucion, reciente).estado == "en_curso"
    assert db.session.get(Ejecucion, terminada).estado == "exito"
    eventos = [e for e in _eventos(app) if e.get("evento") == "ejecucion.interrumpida"]
    assert eventos and vieja in str(eventos[0])


def test_tarea_que_termina_despues_de_marcada_registra_su_resultado_real(app):
    from app.core.ejecuciones import ejecucion, marcar_interrumpidas

    with ejecucion("ejemplo", "demo", proceso="prueba") as ctx:
        assert marcar_interrumpidas(horas=0) == [ctx.ejecucion_id]
        ctx.estado = "interrumpida"  # una tarea no puede fijar estados del núcleo
    assert Ejecucion.query.one().estado == "exito"


def test_cli_tareas_interrumpidas(app):
    vieja = _ejecucion_en_curso(horas_atras=5)
    r = app.test_cli_runner().invoke(args=["tareas", "interrumpidas", "--horas", "4"])
    assert r.exit_code == 0 and "1" in r.output and vieja in r.output
    assert Ejecucion.query.filter_by(estado="interrumpida").count() == 1


# ---------------------------------------------------------------- sin cambios

def _ejecucion_sin_cambios(dias_atras, modulo_id="ejemplo"):
    from app.core.models import ahora_utc
    from app.extensions import db

    momento = ahora_utc() - timedelta(days=dias_atras)
    fila = Ejecucion(modulo_id=modulo_id, tarea="demo", proceso="prueba", estado="sin_cambios", inicio=momento, fin=momento)
    db.session.add(fila)
    db.session.commit()
    return fila.id


def test_tarea_puede_terminar_sin_cambios(app):
    from app.core.ejecuciones import ejecucion, ultimas_ejecuciones

    with ejecucion("ejemplo", "demo", proceso="prueba") as ctx:
        ctx.estado = "sin_cambios"
    assert Ejecucion.query.one().estado == "sin_cambios"
    assert ultimas_ejecuciones("ejemplo") == []
    assert [e.estado for e in ultimas_ejecuciones("ejemplo", incluir_sin_cambios=True)] == ["sin_cambios"]


def test_purga_solo_sin_cambios_antiguas(app):
    from app.core.ejecuciones import mantenimiento_al_iniciar
    from app.extensions import db

    app.config["EJECUCIONES_SIN_CAMBIOS_DIAS"] = 7
    vieja = _ejecucion_sin_cambios(dias_atras=8)
    reciente = _ejecucion_sin_cambios(dias_atras=1)
    exito_viejo = ejecutar_tarea("ejemplo", "demo", proceso="prueba", parametros={"pasos": 1}).id
    fila = db.session.get(Ejecucion, exito_viejo)
    fila.fin = fila.fin - timedelta(days=30)
    db.session.commit()

    mantenimiento_al_iniciar(app)

    assert db.session.get(Ejecucion, vieja) is None
    assert db.session.get(Ejecucion, reciente) is not None
    assert db.session.get(Ejecucion, exito_viejo) is not None  # el historial real no se purga


def test_cli_tareas_purgar(app):
    _ejecucion_sin_cambios(dias_atras=3)
    r = app.test_cli_runner().invoke(args=["tareas", "purgar", "--dias", "2"])
    assert r.exit_code == 0 and "1" in r.output
    assert Ejecucion.query.count() == 0


def test_lista_de_ejecuciones_oculta_sin_cambios_por_defecto(app, entrar_como, admin):
    _ejecucion_sin_cambios(dias_atras=0)
    ejecutar_tarea("ejemplo", "demo", proceso="prueba", parametros={"pasos": 1})
    c = entrar_como(admin)
    assert b"Sin cambios</span>" not in c.get("/admin/ejecuciones").data
    assert b"Sin cambios</span>" in c.get("/admin/ejecuciones?estado=todas").data
    assert b"Sin cambios</span>" in c.get("/admin/ejecuciones?estado=sin_cambios").data


# ---------------------------------------------------------------- ejecución exclusiva

def test_ejecucion_vigente_rechaza_la_nueva_sin_registrarla(app):
    import pytest

    from app.core.ejecuciones import EjecucionEnCurso

    vigente = _ejecucion_en_curso(horas_atras=0.5)
    with pytest.raises(EjecucionEnCurso) as exc:
        ejecutar_tarea("ejemplo", "demo", proceso="prueba")
    assert exc.value.en_curso.id == vigente
    assert Ejecucion.query.count() == 1  # la rechazada no deja registro
    eventos = [e for e in _eventos(app) if e.get("evento") == "ejecucion.omitida_por_concurrencia"]
    assert eventos and eventos[0]["modulo"] == "ejemplo"

    # Otro módulo no se bloquea.
    from app.core.ejecuciones import ejecucion

    with ejecucion("otro_modulo", "x", proceso="prueba"):
        pass


def test_ejecucion_zombie_se_interrumpe_y_da_paso(app):
    app.config["EJECUCIONES_INTERRUMPIDAS_HORAS"] = 2
    zombie = _ejecucion_en_curso(horas_atras=3)
    nueva = ejecutar_tarea("ejemplo", "demo", proceso="prueba", parametros={"pasos": 1})
    from app.extensions import db

    assert db.session.get(Ejecucion, zombie).estado == "interrumpida"
    assert nueva.estado == "exito"


def test_la_base_impide_dos_en_curso_del_mismo_modulo(app):
    """Si dos procesos pasan la verificación a la vez, el índice único decide."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.extensions import db

    _ejecucion_en_curso(horas_atras=0)
    with pytest.raises(IntegrityError):
        _ejecucion_en_curso(horas_atras=0)
    db.session.rollback()


def test_carrera_resuelta_por_el_indice_se_reporta_como_en_curso(app, monkeypatch):
    """Simula que otro proceso insertó entre la verificación y el INSERT."""
    import pytest

    from app.core import ejecuciones
    from app.core.ejecuciones import EjecucionEnCurso

    otro = {}
    original = ejecuciones._en_curso

    def verificacion_que_llega_tarde(modulo_id):
        if not otro:  # la primera consulta ve el módulo libre; justo después "otro proceso" inserta
            resultado = original(modulo_id)
            otro["id"] = _ejecucion_en_curso(horas_atras=0)
            return resultado
        return original(modulo_id)

    monkeypatch.setattr(ejecuciones, "_en_curso", verificacion_que_llega_tarde)
    with pytest.raises(EjecucionEnCurso) as exc:
        ejecutar_tarea("ejemplo", "demo", proceso="prueba")
    assert exc.value.en_curso.id == otro["id"] and Ejecucion.query.count() == 1


def test_pantalla_api_y_cli_informan_la_ejecucion_en_curso(app, entrar_como, autorizado):
    _ejecucion_en_curso(horas_atras=0)
    c = entrar_como(autorizado)
    r = c.post("/m/ejemplo/ejecutar", data={"pasos": "1"}, follow_redirects=True)
    assert "ya tiene una ejecución en curso" in r.get_data(as_text=True)
    r = c.post("/m/ejemplo/api/ejecuciones", json={"pasos": 1})
    assert r.status_code == 409 and r.get_json()["error"] == "ejecucion_en_curso"
    r = app.test_cli_runner().invoke(args=["tareas", "ejecutar", "ejemplo", "demo"])
    assert r.exit_code == 3 and "Omitida" in r.output


def test_accesos_http_no_llenan_el_log_central(app):
    acceso = logging.getLogger("werkzeug")
    acceso.info('127.0.0.1 - - "GET /static/css/automate.css HTTP/1.1" 304 -')
    acceso.warning("advertencia del servidor")
    mensajes = [e["mensaje"] for e in _eventos(app)]
    assert "advertencia del servidor" in mensajes
    assert not any("automate.css" in m for m in mensajes)


# ---------------------------------------------------------------- módulo deshabilitado

def test_modulo_deshabilitado_no_ejecuta_tareas(app):
    import pytest
    from app.core.ejecuciones import ModuloDeshabilitado
    from app.core.models import Modulo
    from app.extensions import db

    db.session.get(Modulo, "ejemplo").activo = False
    db.session.commit()
    with pytest.raises(ModuloDeshabilitado):
        ejecutar_tarea("ejemplo", "demo", proceso="tarea-programada")
    assert Ejecucion.query.count() == 0                        # no se registra nada
    assert any(e["evento"] == "ejecucion.omitida_modulo_deshabilitado" for e in _eventos(app))

    r = app.test_cli_runner().invoke(args=["tareas", "ejecutar", "ejemplo", "demo", "--proceso", "prog"])
    assert r.exit_code == 4 and "deshabilitado" in r.output

    db.session.get(Modulo, "ejemplo").activo = True
    db.session.commit()
    assert ejecutar_tarea("ejemplo", "demo", proceso="prog", parametros={"pasos": 1}).estado == "exito"


# ---------------------------------------------------------------- auditoría Krug (23/11/2026)

def test_filtro_de_usuario_acepta_parte_del_usuario_sin_distinguir_mayusculas(app, entrar_como, autorizado):
    entrar_como(autorizado)                         # deja un evento auth.acceso con usuario "autorizado"
    assert any(e.get("evento") == "auth.acceso" for e in _eventos(app, usuario="AUTORIZ"))
    assert not _eventos(app, usuario="otra-persona")


def test_pantalla_de_logs_pide_el_usuario_stod_no_el_correo(entrar_como, admin):
    html = entrar_como(admin).get("/admin/logs").get_data(as_text=True)
    assert 'placeholder="usuario STOD"' in html and 'placeholder="correo"' not in html


def test_ejecuciones_y_logs_muestran_el_nombre_del_modulo_y_la_fecha_como_el_resto(app, entrar_como, admin, autorizado):
    import re
    c_user = app.test_client()
    entrar(c_user, autorizado.usuario_stod)
    c_user.post("/m/ejemplo/ejecutar", data={"pasos": "1"})
    c = entrar_como(admin)
    for ruta in ("/admin/ejecuciones", "/admin/logs?modulo=ejemplo"):
        html = c.get(ruta).get_data(as_text=True)
        assert 'title="ejemplo">Módulo de ejemplo<' in html, ruta
    logs = c.get("/admin/logs").get_data(as_text=True)
    assert re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}", logs) and not re.search(r"\d{4}-\d{2}-\d{2} \d{2}:", logs)
    assert 'title="core">Hub<' in logs


# ---------------------------------------------------------------- auditoría Krug del 25/11/2026

def test_ejecuciones_la_fila_abre_el_detalle_y_muestra_el_error(app, entrar_como, admin):
    from app.extensions import db
    e = Ejecucion(modulo_id="ejemplo", tarea="demo", proceso="prueba", estado="error",
                  error="No se pudo leer el buzón: tiempo de espera agotado")
    db.session.add(e)
    db.session.commit()
    html = entrar_como(admin).get("/admin/ejecuciones").get_data(as_text=True)
    assert f'<tr data-fila-enlace="/admin/ejecuciones/{e.id}">' in html
    assert f'href="/admin/ejecuciones/{e.id}"' in html   # enlace normal para teclado y lectores
    assert "No se pudo leer el buzón: tiempo de espera agotado</div>" in html


def test_logs_abre_sin_debug_y_todos_lo_incluye(app, entrar_como, admin):
    get_logger("ejemplo").debug("detalle interno", extra={"evento": "prueba.debug"})
    get_logger("ejemplo").info("algo que pasó", extra={"evento": "prueba.info"})
    c = entrar_como(admin)
    por_defecto = c.get("/admin/logs").get_data(as_text=True)
    assert "prueba.info" in por_defecto and "prueba.debug" not in por_defecto
    assert '<option value="INFO" selected>' in por_defecto
    todos = c.get("/admin/logs?nivel=").get_data(as_text=True)
    assert "prueba.debug" in todos and "prueba.info" in todos


# ---------------------------------------------------------------- navegación y modales (25/11/2026)

def _ejecucion_con_error(dias_atras=0):
    from app.core.models import ahora_utc
    from app.extensions import db
    momento = ahora_utc() - timedelta(days=dias_atras)
    e = Ejecucion(modulo_id="ejemplo", tarea="demo", proceso="prueba", estado="error", error="falló", inicio=momento, fin=momento)
    db.session.add(e)
    db.session.commit()
    return e


def test_volver_del_detalle_regresa_a_la_lista_filtrada(app, entrar_como, admin):
    e = _ejecucion_con_error()
    c = entrar_como(admin)
    c.get("/admin/ejecuciones?estado=error&modulo=ejemplo")
    html = c.get(f"/admin/ejecuciones/{e.id}").get_data(as_text=True)
    assert html.count('href="/admin/ejecuciones?estado=error&amp;modulo=ejemplo"') == 2   # «Volver» y el pretítulo


def test_volver_de_un_usuario_regresa_a_la_pagina_de_la_lista(entrar_como, admin, autorizado):
    c = entrar_como(admin)
    c.get("/admin/usuarios?pagina=1")
    html = c.get(f"/admin/usuarios/{autorizado.id}").get_data(as_text=True)
    assert html.count('href="/admin/usuarios?pagina=1"') == 3   # «Volver», pretítulo y «Cancelar»


def test_volver_no_usa_direcciones_ajenas(app, entrar_como, admin):
    e = _ejecucion_con_error()
    c = entrar_como(admin)
    with c.session_transaction() as s:
        s["lista_ejecuciones"] = "//sitio-ajeno.example/admin/ejecuciones"
    html = c.get(f"/admin/ejecuciones/{e.id}").get_data(as_text=True)
    assert "sitio-ajeno" not in html and 'href="/admin/ejecuciones"' in html


def test_detalle_sin_eventos_lo_dice_sin_hablar_de_filtros(app, entrar_como, admin):
    e = _ejecucion_con_error()
    html = entrar_como(admin).get(f"/admin/ejecuciones/{e.id}").get_data(as_text=True)
    assert "Ya no hay eventos de esta ejecución: los logs se conservan" in html
    assert "No hay eventos con esos filtros" not in html
    assert "<th>Ejecución</th>" not in html   # todas las filas serían la misma


def test_detalle_busca_eventos_desde_el_dia_de_la_ejecucion(app, entrar_como, admin):
    import json
    from datetime import date
    app.config["LOG_RETENCION_DIAS"] = 90
    e = _ejecucion_con_error(dias_atras=40)
    dia = date.today() - timedelta(days=40)
    evento = {"ts": f"{dia:%Y-%m-%d}T10:00:00.000-06:00", "nivel": "ERROR", "modulo": "ejemplo", "evento": "prueba.antigua",
              "mensaje": "evento de hace 40 días", "usuario": None, "ejecucion_id": e.id}
    archivo = Path(app.config["LOG_DIR"]) / f"automate-{dia:%Y-%m-%d}.jsonl"
    archivo.write_text(json.dumps(evento) + "\n", encoding="utf-8")
    html = entrar_como(admin).get(f"/admin/ejecuciones/{e.id}").get_data(as_text=True)
    assert "evento de hace 40 días" in html


def test_en_logs_la_ejecucion_lleva_a_su_detalle(app, entrar_como, autorizado, admin):
    c_user = app.test_client()
    entrar(c_user, autorizado.usuario_stod)
    c_user.post("/m/ejemplo/ejecutar", data={"pasos": "1"})
    e = Ejecucion.query.one()
    html = entrar_como(admin).get("/admin/logs?modulo=ejemplo").get_data(as_text=True)
    assert f'href="/admin/ejecuciones/{e.id}"' in html and "ejecucion_id=" not in html.split("<tbody>", 1)[1]


def test_ejecucion_que_ya_no_existe_lleva_a_sus_eventos(entrar_como, admin):
    r = entrar_como(admin).get("/admin/ejecuciones/abc123")
    assert r.status_code == 302 and "/admin/logs?" in r.headers["Location"] and "ejecucion_id=abc123" in r.headers["Location"]
