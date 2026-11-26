"""Dar el rol de Administrador desde «Usuarios y permisos» pide confirmación.

Es escalar privilegios: el formulario de edición lleva ``data-confirmar-si`` sobre la opción
Administrador (``admin/usuario_form.html``) y ``interaccion.js`` abre ``#modal-confirmar`` antes de
enviar. Se prueban los dos caminos: Cancelar no guarda nada y «Sí, dar el rol» sí guarda.

Cada prueba usa su propio servidor (``servidor_aparte``) porque edita un usuario: así no deja
estado cambiado para las demás pruebas de la sesión.
"""
import re

from playwright.sync_api import Page, expect

from .conftest import entrar

TITULO = "¿Dar el rol de Administrador?"
OPERADOR = "qa_operador"


def _rol_en_base(srv, usuario_stod: str) -> tuple[str, int]:
    """Rol y módulos guardados en la base del servidor de QA."""
    from app.core.models import Usuario
    from app.extensions import db

    with srv.app.app_context():
        db.session.expire_all()
        u = Usuario.query.filter_by(usuario_stod=usuario_stod).one()
        return u.rol, u.modulos_ids()


def _abrir_edicion_del_operador(page: Page, srv) -> None:
    """Administración > Usuarios y permisos > clic en la persona, como lo haría alguien."""
    entrar(page, srv.url, "qa_super")
    page.get_by_role("link", name="Usuarios y permisos").click()
    expect(page.get_by_role("heading", name="Usuarios y permisos")).to_be_visible()
    fila = page.locator("tr", has_text=OPERADOR)
    fila.get_by_role("link").first.click()
    expect(page).to_have_url(re.compile(r"/admin/usuarios/\d+$"))
    # Se cambia también el nombre: si el formulario llegara a enviarse al cancelar, ese cambio
    # quedaría guardado y la prueba lo detectaría aunque el rol no hubiera cambiado.
    page.get_by_label("Nombres").fill("Operadora")
    page.get_by_label("Apellidos").fill("De Prueba")


def _opcion(page: Page, nombre: str):
    return page.get_by_role("radio", name=re.compile(rf"^{nombre}\b"))


def _elegir_rol(page: Page, nombre: str) -> None:
    """Clic en la tarjeta del rol, como una persona: el radio de Tabler es invisible (opacity 0)
    y la tarjeta que lo cubre recibe el clic."""
    page.locator("label.form-selectgroup-item", has=_opcion(page, nombre)).click()
    expect(_opcion(page, nombre)).to_be_checked()


def test_marcar_administrador_pide_confirmacion_y_cancelar_no_guarda_nada(page: Page, servidor_aparte, errores_js):
    srv = servidor_aparte()
    rol_antes, modulos_antes = _rol_en_base(srv, OPERADOR)
    assert rol_antes == "usuario"

    _abrir_edicion_del_operador(page, srv)
    url_edicion = page.url
    expect(_opcion(page, "Operador")).to_be_checked()

    envios: list[str] = []
    page.on("request", lambda r: envios.append(r.url) if r.method == "POST" else None)

    _elegir_rol(page, "Administrador")
    page.get_by_role("button", name="Guardar cambios").click()

    modal = page.locator("#modal-confirmar")
    expect(modal).to_be_visible()
    expect(modal.locator("[data-modal-titulo]")).to_have_text(TITULO)
    expect(modal.locator("[data-modal-aceptar]")).to_have_text("Sí, dar el rol")

    modal.get_by_role("button", name="Cancelar").click()
    expect(modal).to_be_hidden()

    # Nada salió hacia el servidor, la página no cambió y no hay aviso de «guardado».
    assert envios == [], f"Se envió el formulario pese a cancelar: {envios}"
    assert page.url == url_edicion
    expect(page.get_by_text("Cambios guardados.")).to_have_count(0)
    # El botón no queda bloqueado con el spinner de data-cargando.
    expect(page.get_by_role("button", name="Guardar cambios")).to_be_enabled()

    # En la base sigue igual.
    assert _rol_en_base(srv, OPERADOR) == (rol_antes, modulos_antes)

    # Y al recargar, la pantalla también lo muestra como Operador.
    page.reload()
    expect(_opcion(page, "Operador")).to_be_checked()


def test_confirmar_si_da_el_rol_de_administrador(page: Page, servidor_aparte, errores_js):
    srv = servidor_aparte()
    _abrir_edicion_del_operador(page, srv)

    _elegir_rol(page, "Administrador")
    page.get_by_role("button", name="Guardar cambios").click()
    modal = page.locator("#modal-confirmar")
    expect(modal.locator("[data-modal-titulo]")).to_have_text(TITULO)
    modal.locator("[data-modal-aceptar]").click()

    expect(page.get_by_text("Cambios guardados.")).to_be_visible()
    expect(_opcion(page, "Administrador")).to_be_checked()
    assert _rol_en_base(srv, OPERADOR)[0] == "admin"


def test_guardar_sin_tocar_el_rol_no_pide_confirmacion(page: Page, servidor_aparte, errores_js):
    """La confirmación es solo para dar el rol: guardar otros cambios no la muestra."""
    srv = servidor_aparte()
    _abrir_edicion_del_operador(page, srv)

    page.get_by_role("button", name="Guardar cambios").click()
    expect(page.get_by_text("Cambios guardados.")).to_be_visible()
    expect(page.locator("#modal-confirmar")).to_be_hidden()
    assert _rol_en_base(srv, OPERADOR)[0] == "usuario"
