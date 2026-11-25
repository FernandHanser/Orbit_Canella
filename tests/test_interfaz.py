"""Patrones de interacción (docs/INTERFAZ.md#spinners-y-confirmaciones): las acciones que tardan
muestran spinner y las que tienen efectos críticos piden confirmación."""


def test_login_muestra_spinner(client):
    html = client.get("/acceso").data.decode()
    assert 'data-cargando="Validando con STOD…"' in html and "js/interaccion.js" in html


def test_deshabilitar_modulo_pide_confirmacion_y_habilitar_no(app, entrar_como, superadmin):
    from app.core.models import Modulo
    from app.extensions import db

    c = entrar_como(superadmin)
    html = c.get("/admin/modulos").data.decode()
    assert 'data-cargando="Sincronizando…"' in html
    assert "¿Deshabilitar «Módulo de ejemplo»?" in html

    db.session.get(Modulo, "ejemplo").activo = False
    db.session.commit()
    html = c.get("/admin/modulos").data.decode()
    assert "¿Deshabilitar «Módulo de ejemplo»?" not in html and 'data-cargando="Habilitando…"' in html


def test_formularios_de_administracion_con_spinner(app, entrar_como, admin, autorizado):
    c = entrar_como(admin)
    assert 'data-cargando="Guardando…"' in c.get(f"/admin/usuarios/{autorizado.id}").data.decode()
    assert 'data-cargando="Buscando…"' in c.get("/admin/logs").data.decode()


# ---------------------------------------------------------------- tarjetas del inicio

def test_tarjeta_muestra_ultima_ejecucion_y_titulo_de_seccion(app, entrar_como, autorizado):
    from app.core.ejecuciones import ejecutar_tarea

    c = entrar_como(autorizado)
    html = c.get("/").data.decode()
    import re
    assert "Mis automatizaciones" in html and "MÓDULO DE EJEMPLO" not in html
    # Mismo nombre que en el menú (regla «un módulo, un nombre»), no en mayúsculas.
    assert re.search(r'<h3 class="card-title mb-1">\s*Módulo de ejemplo', html)
    assert "Sin ejecuciones" in html and "Abrir" in html

    ejecutar_tarea("ejemplo", "demo", proceso="prog", parametros={"pasos": 1})
    html = c.get("/").data.decode()
    assert "Última revisión hace un momento" in html and "status-green" in html


def test_filtro_hace(app):
    from datetime import datetime, timedelta, timezone
    hace = app.jinja_env.filters["hace"]
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    assert hace(ahora) == "hace un momento"
    assert hace(ahora - timedelta(minutes=4, seconds=5)) == "hace 4 min"
    assert hace(ahora - timedelta(hours=3)) == "hace 3 h"
    assert hace(ahora - timedelta(days=1, hours=2)) == "ayer"
    assert hace(None) == "—"


# ---------------------------------------------------------------- avatares de personas

def test_iniciales_y_color_estable(app):
    from app.core.models import Usuario
    u = Usuario(usuario_stod="jperez", nombre="JPEREZ", nombres="Juan Carlos", apellidos="Pérez Gómez")
    assert u.iniciales == "JP"
    assert u.color_avatar == Usuario(usuario_stod="jperez", nombre="x").color_avatar   # no depende del nombre
    assert u.color_avatar in Usuario.COLORES_AVATAR
    assert Usuario(usuario_stod="fhanser", nombre="FHANSER").iniciales == "FH"          # sin nombre registrado


def test_avatar_en_menu_lista_y_detalle(app, entrar_como, admin, autorizado):
    c = entrar_como(admin)
    menu = c.get("/").get_data(as_text=True)
    assert f'avatar avatar-rounded avatar-sm bg-{admin.color_avatar}-lt' in menu and f">{admin.iniciales}</span>" in menu
    lista = c.get("/admin/usuarios").get_data(as_text=True)
    assert f">{autorizado.iniciales}</span>" in lista
    detalle = c.get(f"/admin/usuarios/{autorizado.id}").get_data(as_text=True)
    assert "avatar-xl" in detalle



# ---------------------------------------------------------------- módulo Expedientes de Seguros

def test_expedientes_spinners_y_confirmaciones(app, entrar_como, monkeypatch, tmp_path):
    import io
    from datetime import date
    from pypdf import PdfWriter
    from app.core.models import Usuario
    from app.modulos.expedientes_seguros import servicios
    from app.modulos.expedientes_seguros.sap import Anexo, Llamada, Pendiente
    from .conftest import crear_usuario

    w = PdfWriter(); w.add_blank_page(612, 792); b = io.BytesIO(); w.write(b)
    ruta = tmp_path / "1.pdf"; ruta.write_bytes(b.getvalue())

    class Sap:
        def buscar_llamada(self, call_id):
            return Llamada(7, 7, "C1", "X", "", "", "1602", "", (Anexo(1, str(ruta), "1.pdf", None),), None)

        def pendientes(self, ceco):
            return [Pendiente(7, "C1", "X", "", date.today(), date.today())]

    monkeypatch.setattr(servicios, "crear_repositorio", lambda: Sap())
    app.instance_path = str(tmp_path / "instance")
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))

    inicio = c.get("/m/expedientes_seguros/").get_data(as_text=True)
    assert 'data-cargando="Abriendo…"' in inicio and 'data-cargando="Buscando…"' in inicio
    # Buscar y Armar consultan SAP: además, pantalla de carga con el logo de SAP.
    assert inicio.count("data-cargando-pagina=") == 2 and "data-cargando-logo=" in inicio
    assert 'data-cargando="Filtrando…"' in inicio

    visor = c.get("/m/expedientes_seguros/llamadas/7?ceco=1602").get_data(as_text=True)
    assert 'data-cargando="Generando paquete…"' in visor
    assert 'data-confirmar-si="#advertencias[data-hay]"' in visor and '<span id="advertencias" hidden></span>' in visor
    assert 'class="pagina-cargando"' in visor and 'id="modal-pagina-cargando"' in visor

    parametros = c.get("/m/expedientes_seguros/correo-por-defecto").get_data(as_text=True)
    assert "¿Cambiar el correo por defecto?" in parametros


# ---------------------------------------------------------------- menú que se oculta

def test_menu_se_puede_ocultar_en_todas_las_pantallas_con_menu(app, entrar_como, autorizado):
    # menu.js va en un bloque propio del layout (head_hub): los módulos que reemplazan «head»
    # sin super() (p. ej. el visor de Expedientes) no lo pierden.
    c = entrar_como(autorizado)
    html = c.get("/").data.decode()
    assert "js/menu.js" in html and "data-menu-ocultar" in html and "data-menu-mostrar" in html
    assert html.index("js/menu.js") < html.index("<body")      # antes de pintar: sin parpadeo
    assert 'id="menu-principal"' in html and 'aria-controls="menu-principal"' in html


def test_pantallas_publicas_sin_menu_no_cargan_menu_js(client):
    assert "js/menu.js" not in client.get("/acceso").data.decode()


def test_administracion_no_remite_a_archivos_del_codigo(entrar_como, superadmin):
    # La pantalla la usa Contabilidad: no puede abrir docs/GLOSARIO.md ni app/modulos/<id>/__init__.py.
    c = entrar_como(superadmin)
    usuarios = c.get("/admin/usuarios").get_data(as_text=True)
    modulos = c.get("/admin/modulos").get_data(as_text=True)
    assert "docs/GLOSARIO.md" not in usuarios and "__init__.py" not in modulos
    assert "alert-info" not in usuarios          # sin el aviso largo antes de la tabla


# ---------------------------------------------------------------- auditoría Krug del 25/11/2026

def test_inicio_sin_pretitulo_repetido(entrar_como, autorizado):
    html = entrar_como(autorizado).get("/").data.decode()
    # El nombre del hub ya está en la marca del menú: el encabezado del inicio no lo repite.
    assert '<div class="page-pretitle">' not in html and "Hola," in html


def test_usuarios_el_nombre_abre_la_edicion_y_la_accion_queda_fija(entrar_como, admin, autorizado):
    html = entrar_como(admin).get("/admin/usuarios").data.decode()
    url = f"/admin/usuarios/{autorizado.id}"
    assert f'<tr data-fila-enlace="{url}">' in html
    assert f'<a href="{url}" class="text-reset">' in html
    assert '<td class="col-acciones">' in html and 'th class="w-1 col-acciones"' in html


def test_usuarios_admin_no_puede_abrir_al_superadmin(entrar_como, admin, superadmin):
    html = entrar_como(admin).get("/admin/usuarios").data.decode()
    assert f"/admin/usuarios/{superadmin.id}" not in html


def test_catalogo_con_acciones_fijas(entrar_como, superadmin):
    html = entrar_como(superadmin).get("/admin/modulos").data.decode()
    assert 'th class="w-1 col-acciones"' in html and '<td class="col-acciones">' in html
