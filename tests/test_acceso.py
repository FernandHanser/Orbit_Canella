"""Inicio de sesión con usuarios de STOD, autorización por módulo y administración."""
import base64
import hashlib
import re
from datetime import timedelta

import pytest

from app.core.identidad import Identidad
from app.core.models import IntentoAcceso, Modulo, Usuario, ahora_utc
from app.extensions import db
from app.integraciones.stod import verificar_hash_membership

from .conftest import CONTRASENA, crear_usuario, entrar, stod

# Nombre y apellido son obligatorios al registrar y al editar (STOD no los guarda).
NOMBRE = {"nombres": "Ana María", "apellidos": "López Pérez"}


# ---------------------------------------------------------------- usuario sin sesión

def test_sin_sesion_redirige_al_acceso(client):
    r = client.get("/")
    assert r.status_code == 302 and "/acceso" in r.headers["Location"]


def test_sin_sesion_modulo_conserva_destino(client):
    r = client.get("/m/ejemplo/")
    assert r.status_code == 302 and "/acceso?siguiente=/m/ejemplo/" in r.headers["Location"]


def test_sin_sesion_api_responde_401_json(client):
    r = client.get("/m/ejemplo/api/estado")
    assert r.status_code == 401 and r.get_json()["error"] == "no_autenticado"


def test_sin_sesion_admin_redirige(client):
    assert client.get("/admin/usuarios").status_code == 302


def test_salud_es_publica(client):
    assert client.get("/salud").get_json() == {"estado": "ok"}


def test_pantalla_de_acceso(client):
    html = client.get("/acceso").get_data(as_text=True)
    assert "ORBIT" in html and "Hub de Automatizaciones de Contabilidad Canella" in html
    assert "Usuario STOD" in html


# ---------------------------------------------------------------- inicio de sesión con STOD

def test_primer_ingreso_crea_usuario_sin_modulos(app, client):
    crear_usuario("nuevo", en_hub=False)
    assert entrar(client, "nuevo").status_code == 302
    u = Usuario.query.filter_by(usuario_stod="nuevo").one()
    assert (u.rol, u.modulos_ids(), u.email, u.nombre) == ("usuario", set(), "nuevo@canella.test", "NUEVO")
    assert u.ultimo_acceso is not None and u.stod_verificado_en is not None
    assert "Aún no tienes automatizaciones asignadas" in client.get("/").get_data(as_text=True)


def test_usuario_sin_distinguir_mayusculas(app, client, autorizado):
    assert entrar(client, "  AUTORIZADO ").status_code == 302
    assert Usuario.query.count() == 1


def test_contrasena_incorrecta(client, autorizado):
    r = entrar(client, "autorizado", "incorrecta")
    assert r.status_code == 200 and "Usuario o contraseña incorrectos" in r.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_usuario_inexistente_no_se_registra(app, client):
    r = entrar(client, "fantasma")
    assert "Usuario o contraseña incorrectos" in r.get_data(as_text=True)
    assert Usuario.query.count() == 0


def test_inactivo_en_stod_no_entra(app, client):
    crear_usuario("inactivo", activo_stod=False, en_hub=False)
    r = entrar(client, "inactivo")
    assert "inactivo o bloqueado en STOD" in r.get_data(as_text=True)
    assert client.get("/").status_code == 302 and Usuario.query.count() == 0


def test_deshabilitado_en_hub_no_entra(client, app):
    crear_usuario("bloqueadohub", activo=False, modulos=["ejemplo"])
    r = entrar(client, "bloqueadohub")
    assert "está deshabilitado" in r.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_stod_caido_al_iniciar_sesion(client, autorizado):
    stod().disponible = False
    r = entrar(client, "autorizado")
    assert "No se pudo validar tu usuario con STOD" in r.get_data(as_text=True)
    assert IntentoAcceso.query.count() == 0  # no cuenta como intento fallido


def test_bloqueo_por_intentos_incluso_sin_usuario_local(app, client):
    crear_usuario("persona", en_hub=False)
    for _ in range(app.config["LOGIN_MAX_INTENTOS"]):
        entrar(client, "persona", "incorrecta")
    r = entrar(client, "persona")  # contraseña correcta, pero bloqueado
    assert "Demasiados intentos fallidos" in r.get_data(as_text=True)
    assert Usuario.query.count() == 0


def test_bloqueo_vence(app, client, autorizado):
    for _ in range(app.config["LOGIN_MAX_INTENTOS"]):
        entrar(client, "autorizado", "incorrecta")
    for intento in IntentoAcceso.query.all():
        intento.creado_en = ahora_utc() - timedelta(minutes=app.config["LOGIN_BLOQUEO_MINUTOS"] + 1)
    db.session.commit()
    assert entrar(client, "autorizado").status_code == 302
    assert IntentoAcceso.query.filter_by(usuario="autorizado").count() == 0


def test_actualiza_datos_desde_stod(app, client, autorizado):
    stod().registrar("autorizado", CONTRASENA, email="nuevo.correo@canella.test")
    entrar(client, "autorizado")
    u = db.session.get(Usuario, autorizado.id)
    assert (u.email, u.nombre) == ("nuevo.correo@canella.test", "NUEVO CORREO")


def test_redireccion_abierta_bloqueada(client, autorizado):
    r = client.post("/acceso?siguiente=//sitio-externo.test/x", data={"usuario": "autorizado", "contrasena": CONTRASENA})
    assert r.headers["Location"] == "/"


def test_redireccion_a_destino_interno(client, autorizado):
    r = client.post("/acceso?siguiente=/m/ejemplo/", data={"usuario": "autorizado", "contrasena": CONTRASENA})
    assert r.headers["Location"] == "/m/ejemplo/"


def test_cerrar_sesion_solo_por_post(entrar_como, autorizado):
    c = entrar_como(autorizado)
    assert c.get("/salir").status_code == 405
    assert c.post("/salir").status_code == 302
    assert c.get("/").status_code == 302


def test_ya_no_existe_cambio_de_contrasena(entrar_como, autorizado):
    assert entrar_como(autorizado).get("/cuenta/contrasena").status_code == 404


# ---------------------------------------------------------------- revalidación con STOD

def _vencer_verificacion(usuario):
    u = db.session.get(Usuario, usuario.id)
    u.stod_verificado_en = ahora_utc() - timedelta(hours=1)
    db.session.commit()


def test_revalidacion_cierra_sesion_si_se_inactiva_en_stod(entrar_como, autorizado):
    c = entrar_como(autorizado)
    stod().cambiar_estado("autorizado", activo=False)
    assert c.get("/").status_code == 200  # aún dentro del intervalo de revalidación
    _vencer_verificacion(autorizado)
    r = c.get("/")
    assert r.status_code == 302 and "/acceso" in r.headers["Location"]
    assert c.get("/").status_code == 302


def test_revalidacion_api_responde_401(entrar_como, autorizado):
    c = entrar_como(autorizado)
    stod().cambiar_estado("autorizado", activo=False)
    _vencer_verificacion(autorizado)
    assert c.get("/m/ejemplo/api/estado").status_code == 401


def test_revalidacion_con_stod_caido_mantiene_la_sesion(entrar_como, autorizado):
    c = entrar_como(autorizado)
    stod().disponible = False
    _vencer_verificacion(autorizado)
    assert c.get("/").status_code == 200


def test_revalidacion_exitosa_actualiza_la_fecha(entrar_como, autorizado):
    c = entrar_como(autorizado)
    _vencer_verificacion(autorizado)
    c.get("/")
    assert db.session.get(Usuario, autorizado.id).stod_verificado_en > ahora_utc() - timedelta(minutes=1)


# ---------------------------------------------------------------- hash de ASP.NET Membership

def test_verificacion_hash_membership():
    salt = base64.b64encode(b"0123456789abcdef").decode()
    guardado = base64.b64encode(hashlib.sha1(b"0123456789abcdef" + "Contraseña1".encode("utf-16le")).digest()).decode()
    assert verificar_hash_membership("Contraseña1", guardado, salt)
    assert not verificar_hash_membership("contraseña1", guardado, salt)
    assert not verificar_hash_membership("Contraseña1", guardado, "no-es-base64!!")
    assert not verificar_hash_membership("Contraseña1", "", salt)


def test_nombre_visible():
    assert Identidad("1", "jperez", "juan.perez@canella.com.gt", True).nombre_visible == "JUAN PEREZ"
    assert Identidad("1", "jperez", None, True).nombre_visible == "JPEREZ"


def test_proveedor_simulado_solo_en_pruebas(tmp_path):
    from app import create_app

    with pytest.raises(RuntimeError, match="solo se permite"):
        create_app("development", AUTH_PROVEEDOR="simulado", SECRET_KEY="x", LOG_DIR=str(tmp_path),
                   SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", AUTO_SINCRONIZAR_MODULOS=False)


# ---------------------------------------------------------------- autorización por módulo

def test_autorizado_ve_su_modulo_y_entra(entrar_como, autorizado):
    c = entrar_como(autorizado)
    inicio = c.get("/").get_data(as_text=True)
    assert "Módulo de ejemplo" in inicio and "/m/ejemplo/" in inicio
    assert c.get("/m/ejemplo/").status_code == 200


def test_autorizado_ejecuta_tarea_web(entrar_como, autorizado):
    from app.core.models import Ejecucion

    c = entrar_como(autorizado)
    r = c.post("/m/ejemplo/ejecutar", data={"pasos": "2"}, follow_redirects=True)
    assert r.status_code == 200 and "completada" in r.get_data(as_text=True)
    e = Ejecucion.query.one()
    assert (e.modulo_id, e.estado, e.usuario_id, e.iniciado_por) == ("ejemplo", "exito", autorizado.id, autorizado.nombre_completo)


def test_usuario_no_entra_a_admin(entrar_como, autorizado):
    r = entrar_como(autorizado).get("/admin/usuarios")
    assert r.status_code == 403 and "exclusiva de administradores" in r.get_data(as_text=True)


def test_sin_permiso_no_ve_el_modulo(entrar_como, sin_permiso):
    html = entrar_como(sin_permiso).get("/").get_data(as_text=True)
    assert "/m/ejemplo/" not in html and "Aún no tienes automatizaciones asignadas" in html


def test_sin_permiso_url_directa_403(entrar_como, sin_permiso):
    c = entrar_como(sin_permiso)
    r = c.get("/m/ejemplo/")
    assert r.status_code == 403 and "Acceso denegado" in r.get_data(as_text=True)
    assert c.post("/m/ejemplo/ejecutar", data={"pasos": "1"}).status_code == 403


def test_ningun_rol_da_acceso_implicito_a_modulos(entrar_como, superadmin):
    assert entrar_como(superadmin).get("/m/ejemplo/").status_code == 403


def test_api_sin_permiso_403_json(entrar_como, sin_permiso):
    c = entrar_como(sin_permiso)
    r = c.get("/m/ejemplo/api/estado")
    assert r.status_code == 403 and r.get_json()["error"] == "acceso_denegado"
    assert c.post("/m/ejemplo/api/ejecuciones", json={}).status_code == 403


def test_api_con_permiso(entrar_como, autorizado):
    c = entrar_como(autorizado)
    r = c.post("/m/ejemplo/api/ejecuciones", json={"pasos": 1})
    assert r.status_code == 201 and r.get_json()["estado"] == "exito"
    datos = c.get("/m/ejemplo/api/estado").get_json()
    assert datos["usuario"] == "autorizado" and len(datos["ultimas_ejecuciones"]) == 1


def test_api_404_json(entrar_como, autorizado):
    r = entrar_como(autorizado).get("/m/ejemplo/api/no-existe")
    assert r.status_code == 404 and r.get_json()["error"] == "no_encontrado"


def test_modulo_deshabilitado_no_disponible(entrar_como, autorizado):
    db.session.get(Modulo, "ejemplo").activo = False
    db.session.commit()
    c = entrar_como(autorizado)
    r = c.get("/m/ejemplo/")
    assert r.status_code == 503 and "Módulo no disponible" in r.get_data(as_text=True)
    assert c.get("/m/ejemplo/api/estado").status_code == 503
    assert "/m/ejemplo/" not in c.get("/").get_data(as_text=True)


# ---------------------------------------------------------------- administración y jerarquía

def _cliente(app, usuario):
    c = app.test_client()
    assert entrar(c, usuario.usuario_stod).status_code == 302
    return c


def test_admin_asigna_y_retira_acceso(app, admin, sin_permiso):
    c_admin, c_user = _cliente(app, admin), _cliente(app, sin_permiso)
    assert c_user.get("/m/ejemplo/").status_code == 403
    assert c_admin.post(f"/admin/usuarios/{sin_permiso.id}", data={**NOMBRE, "activo": "y", "modulos": ["ejemplo"]}).status_code == 302
    assert c_user.get("/m/ejemplo/").status_code == 200
    assert c_admin.post(f"/admin/usuarios/{sin_permiso.id}", data={**NOMBRE, "activo": "y"}).status_code == 302
    assert c_user.get("/m/ejemplo/").status_code == 403


def test_admin_deshabilita_usuario_y_cierra_su_sesion(app, admin, autorizado):
    c_admin, c_user = _cliente(app, admin), _cliente(app, autorizado)
    c_admin.post(f"/admin/usuarios/{autorizado.id}", data={**NOMBRE, "modulos": ["ejemplo"]})
    assert db.session.get(Usuario, autorizado.id).activo is False
    assert c_user.get("/").status_code == 302


def test_prerregistro_con_modulos(app, entrar_como, admin):
    crear_usuario("futuro", en_hub=False)
    c = entrar_como(admin)
    r = c.post("/admin/usuarios/nuevo", data={**NOMBRE, "usuario_stod": "Futuro", "modulos": ["ejemplo"]})
    assert r.status_code == 302
    u = Usuario.query.filter_by(usuario_stod="futuro").one()
    assert u.modulos_ids() == {"ejemplo"} and u.pendiente_primer_ingreso and u.rol == "usuario"
    c.post("/salir")
    assert entrar(c, "futuro").status_code == 302
    assert c.get("/m/ejemplo/").status_code == 200  # ya tiene su módulo al primer ingreso


def test_prerregistro_valida_contra_stod(app, entrar_como, admin, autorizado):
    c = entrar_como(admin)
    assert "no existe en STOD" in c.post("/admin/usuarios/nuevo", data={**NOMBRE, "usuario_stod": "fantasma"}).get_data(as_text=True)
    assert "ya está registrado" in c.post("/admin/usuarios/nuevo", data={**NOMBRE, "usuario_stod": "autorizado"}).get_data(as_text=True)
    stod().disponible = False
    crear_usuario("otro", en_hub=False)
    assert "No se pudo consultar STOD" in c.post("/admin/usuarios/nuevo", data={**NOMBRE, "usuario_stod": "otro"}).get_data(as_text=True)
    assert Usuario.query.filter_by(usuario_stod="otro").first() is None


def test_prerregistro_de_inactivo_en_stod_avisa(app, entrar_como, admin):
    crear_usuario("dormido", activo_stod=False, en_hub=False)
    r = entrar_como(admin).post("/admin/usuarios/nuevo", data={**NOMBRE, "usuario_stod": "dormido"}, follow_redirects=True)
    assert "inactivo o bloqueado en STOD" in r.get_data(as_text=True)


def test_admin_no_cambia_roles_ni_se_deshabilita(app, entrar_como, admin, sin_permiso):
    c = entrar_como(admin)
    c.post(f"/admin/usuarios/{sin_permiso.id}", data={**NOMBRE, "activo": "y", "rol": "admin"})
    assert db.session.get(Usuario, sin_permiso.id).rol == "usuario"
    c.post(f"/admin/usuarios/{admin.id}", data=dict(NOMBRE))  # intenta deshabilitarse
    assert db.session.get(Usuario, admin.id).activo is True


def test_admin_no_deshabilita_a_otro_admin(app, entrar_como, admin):
    otro = crear_usuario("admin2", rol=Usuario.ROL_ADMIN)
    entrar_como(admin).post(f"/admin/usuarios/{otro.id}", data=dict(NOMBRE))
    assert db.session.get(Usuario, otro.id).activo is True


def test_admin_no_edita_al_superadmin(app, entrar_como, admin, superadmin):
    c = entrar_como(admin)
    assert c.get(f"/admin/usuarios/{superadmin.id}").status_code == 403
    assert c.post(f"/admin/usuarios/{superadmin.id}", data=dict(NOMBRE)).status_code == 403


def test_superadmin_nombra_y_quita_administradores(app, superadmin, sin_permiso):
    c_super, c_user = _cliente(app, superadmin), _cliente(app, sin_permiso)
    c_super.post(f"/admin/usuarios/{sin_permiso.id}", data={**NOMBRE, "activo": "y", "rol": "admin"})
    assert db.session.get(Usuario, sin_permiso.id).rol == "admin"
    assert c_user.get("/").status_code == 302  # cambio de rol: vuelve a iniciar sesión
    entrar(c_user, "sinpermiso")
    assert c_user.get("/admin/usuarios").status_code == 200
    c_super.post(f"/admin/usuarios/{sin_permiso.id}", data={**NOMBRE, "activo": "y", "rol": "usuario"})
    assert db.session.get(Usuario, sin_permiso.id).rol == "usuario"


def test_superadmin_no_se_modifica_por_la_web(app, entrar_como, superadmin):
    entrar_como(superadmin).post(f"/admin/usuarios/{superadmin.id}", data={**NOMBRE, "rol": "usuario"})
    u = db.session.get(Usuario, superadmin.id)
    assert (u.rol, u.activo) == ("superadmin", True)


def test_catalogo_solo_superadmin(app, admin, superadmin):
    c_admin, c_super = _cliente(app, admin), _cliente(app, superadmin)
    assert c_admin.get("/admin/modulos").status_code == 403
    assert "Catálogo de módulos" not in c_admin.get("/admin/usuarios").get_data(as_text=True)
    c_admin.post("/admin/modulos/ejemplo/estado", data={"activo": "0"})
    assert db.session.get(Modulo, "ejemplo").activo is True
    assert c_super.get("/admin/modulos").status_code == 200
    c_super.post("/admin/modulos/ejemplo/estado", data={"activo": "0"})
    assert db.session.get(Modulo, "ejemplo").activo is False


def test_pantallas_de_admin_renderizan(entrar_como, superadmin, autorizado):
    c = entrar_como(superadmin)
    for ruta in ["/admin/usuarios", "/admin/usuarios/nuevo", f"/admin/usuarios/{autorizado.id}",
                 f"/admin/usuarios/{superadmin.id}", "/admin/modulos", "/admin/ejecuciones", "/admin/logs", "/no-existe"]:
        r = c.get(ruta)
        assert r.status_code in (200, 404), ruta
        assert "ORBIT Canella" in r.get_data(as_text=True), ruta


def test_cabeceras_de_seguridad(client):
    r = client.get("/acceso")
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"


# ---------------------------------------------------------------- CSRF

def test_csrf_activo_en_formularios_y_api(tmp_path):
    from app import create_app
    from app.core.catalogo import sincronizar_catalogo

    from .conftest import aislar_peticiones

    def token_de(ruta):
        html = c.get(ruta).get_data(as_text=True)
        return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)

    app = create_app("testing", LOG_DIR=str(tmp_path / "logs"), WTF_CSRF_ENABLED=True)
    aislar_peticiones(app)
    with app.app_context():
        db.create_all()
        sincronizar_catalogo()
        crear_usuario("csrf", modulos=["ejemplo"])
        c = app.test_client()
        entrar(c, "csrf")  # sin token: no autentica
        assert c.get("/").status_code == 302
        token = token_de("/acceso")
        assert c.post("/acceso", data={"usuario": "csrf", "contrasena": CONTRASENA, "csrf_token": token}).status_code == 302
        token = token_de("/m/ejemplo/")  # el inicio de sesión renueva la sesión
        assert c.post("/m/ejemplo/ejecutar", data={"pasos": "1"}).status_code == 400
        assert c.post("/m/ejemplo/api/ejecuciones", json={}).status_code == 400
        assert c.post("/m/ejemplo/api/ejecuciones", json={}, headers={"X-CSRFToken": token}).status_code == 201
        db.session.remove()
        db.drop_all()


def test_database_url_es_obligatoria(tmp_path):
    from app import create_app

    with pytest.raises(RuntimeError, match="DATABASE_URL es obligatoria"):
        create_app("development", SQLALCHEMY_DATABASE_URI=None, SECRET_KEY="x", LOG_DIR=str(tmp_path))


# ---------------------------------------------------------------- rol al registrar

def test_superadmin_elige_el_rol_al_registrar(entrar_como, superadmin):
    from .conftest import stod
    stod().registrar("nuevo.admin", "x", email="nuevo.admin@canella.test")
    c = entrar_como(superadmin)
    html = c.get("/admin/usuarios/nuevo").data.decode()
    assert 'name="rol" value="admin"' in html
    c.post("/admin/usuarios/nuevo", data={**NOMBRE, "usuario_stod": "nuevo.admin", "rol": "admin"})
    assert Usuario.query.filter_by(usuario_stod="nuevo.admin").one().rol == Usuario.ROL_ADMIN


def test_admin_solo_registra_usuarios_aunque_fuerce_el_rol(entrar_como, admin):
    from .conftest import stod
    stod().registrar("otro.nuevo", "x", email="otro.nuevo@canella.test")
    c = entrar_como(admin)
    html = c.get("/admin/usuarios/nuevo").data.decode()
    assert 'name="rol"' not in html and "Solo el superadministrador puede registrar administradores" in html
    c.post("/admin/usuarios/nuevo", data={**NOMBRE, "usuario_stod": "otro.nuevo", "rol": "superadmin"})
    assert Usuario.query.filter_by(usuario_stod="otro.nuevo").one().rol == Usuario.ROL_USUARIO


def test_lista_de_usuarios_explica_los_roles(entrar_como, admin):
    html = entrar_como(admin).get("/admin/usuarios").data.decode()
    assert "Opera los módulos que tenga asignados" in html and "Se asigna solo por consola" in html and "Operador" in html


def test_glosario_coincide_con_la_fuente_de_roles():
    from pathlib import Path
    from app.core.roles import ROLES
    glosario = (Path(__file__).parent.parent / "docs" / "GLOSARIO.md").read_text(encoding="utf-8")
    for rol in ROLES:
        assert f"**{rol.nombre}** | {rol.descripcion}" in glosario, rol.clave


def test_dar_rol_admin_pide_confirmacion(entrar_como, superadmin, autorizado):
    c = entrar_como(superadmin)
    for url in ("/admin/usuarios/nuevo", f"/admin/usuarios/{autorizado.id}"):
        html = c.get(url).data.decode()
        assert 'data-confirmar-si="input[name=rol][value=admin]:checked"' in html, url
    assert "Operador" in html and 'name="rol" value="usuario"' in html


# ---------------------------------------------------------------- nombre real (STOD no lo guarda)

def test_registrar_exige_nombre_y_apellido(entrar_como, admin):
    stod().registrar("sin.nombre", "x", email="sin.nombre@canella.test")
    c = entrar_como(admin)
    for datos, mensaje in [
        ({"usuario_stod": "sin.nombre", "apellidos": "López"}, "Indica nombres."),
        ({"usuario_stod": "sin.nombre", "nombres": "Ana"}, "Indica apellidos."),
        ({"usuario_stod": "sin.nombre", "nombres": "Ana3", "apellidos": "López"}, "Solo letras"),
    ]:
        r = c.post("/admin/usuarios/nuevo", data=datos)
        assert r.status_code == 200 and mensaje in r.get_data(as_text=True), mensaje
    assert Usuario.query.filter_by(usuario_stod="sin.nombre").first() is None

    c.post("/admin/usuarios/nuevo", data={"usuario_stod": "sin.nombre", "nombres": "  Ana   María ", "apellidos": "López"})
    u = Usuario.query.filter_by(usuario_stod="sin.nombre").one()
    assert (u.nombres, u.apellidos, u.nombre_completo, u.primer_nombre) == ("Ana María", "López", "Ana María López", "Ana")


def test_se_muestra_el_nombre_y_stod_no_lo_sobrescribe(client, admin):
    u = crear_usuario("jperez", modulos=["ejemplo"])
    u.nombres, u.apellidos = "Juan", "Pérez"
    db.session.commit()
    entrar(client, "jperez")                             # el ingreso actualiza datos desde STOD
    db.session.refresh(u)
    assert (u.nombres, u.apellidos) == ("Juan", "Pérez")
    html = client.get("/").get_data(as_text=True)
    assert "Hola, Juan" in html and "Juan Pérez" in html


def test_lista_marca_a_quien_no_tiene_nombre(entrar_como, admin, autorizado):
    html = entrar_como(admin).get("/admin/usuarios").get_data(as_text=True)
    assert "Sin nombre registrado" in html


# ---------------------------------------------------------------- tope de tamaño de las peticiones

def test_tope_de_subida_por_defecto(app):
    assert app.config["MAX_CONTENT_LENGTH"] == 25 * 1024 * 1024


def test_peticion_demasiado_grande_se_rechaza_con_413_en_espanol(app, client):
    # El tope lo pone el hub para todos los módulos: la petición se corta antes de que una vista
    # (o la validación CSRF) lea el cuerpo, así un módulo que olvide su límite no llena el disco.
    app.config["MAX_CONTENT_LENGTH"] = 1024
    r = client.post("/acceso", data={"usuario": "x", "contrasena": "y" * 2048})
    assert r.status_code == 413
    html = r.get_data(as_text=True)
    assert "Archivo demasiado grande" in html and "1 KB" in html


def test_peticion_demasiado_grande_en_api_responde_json(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 1024
    r = client.post("/acceso", data={"usuario": "x", "contrasena": "y" * 2048}, headers={"Accept": "application/json"})
    assert r.status_code == 413 and r.get_json()["error"] == "demasiado_grande"
