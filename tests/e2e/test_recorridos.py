"""Recorridos base del hub en un navegador real: lo que una persona hace todos los días.

Cubren lo que ``test_client`` no puede: JavaScript ejecutándose bajo la CSP real, modales,
spinners y la cuenta regresiva de la sesión.
"""
import re

from playwright.sync_api import Page, expect

from .conftest import entrar


def test_login_correcto_lleva_al_inicio_sin_errores_js(page: Page, servidor, errores_js):
    entrar(page, servidor.url, "qa_operador")
    expect(page.get_by_role("heading", name="Mis automatizaciones")).to_be_visible()


def test_login_incorrecto_avisa_en_espanol_y_no_entra(page: Page, servidor):
    page.goto(f"{servidor.url}/acceso")
    page.locator("#usuario").fill("qa_operador")
    page.locator("#contrasena").fill("no-es-la-clave")
    page.get_by_role("button", name="Entrar").click()
    expect(page).to_have_url(re.compile(r"/acceso"))
    # Mensaje genérico a propósito: no revela si el usuario existe (MENSAJE_GENERICO en core/auth.py).
    expect(page.get_by_text("Usuario o contraseña incorrectos.")).to_be_visible()


def test_ojo_muestra_y_oculta_la_contrasena(page: Page, servidor, errores_js):
    page.goto(f"{servidor.url}/acceso")
    clave = page.locator("#contrasena")
    expect(clave).to_have_attribute("type", "password")
    page.get_by_role("button", name="Mostrar contraseña").click()
    expect(clave).to_have_attribute("type", "text")


def test_operador_entra_a_un_modulo_asignado(page: Page, servidor, errores_js):
    entrar(page, servidor.url, "qa_operador")
    page.goto(f"{servidor.url}/m/ejemplo/")
    expect(page).to_have_url(re.compile(r"/m/ejemplo/$"))
    expect(page.locator("body")).not_to_contain_text("No tienes acceso")


def test_sin_modulo_asignado_ve_acceso_denegado(page: Page, servidor):
    entrar(page, servidor.url, "qa_sin_modulos")
    respuesta = page.goto(f"{servidor.url}/m/ejemplo/")
    assert respuesta.status == 403
    expect(page.locator("body")).to_contain_text("No tienes acceso")


def test_deshabilitar_un_modulo_pide_confirmacion_y_cancelar_no_cambia_nada(page: Page, servidor, errores_js):
    entrar(page, servidor.url, "qa_super")
    page.goto(f"{servidor.url}/admin/modulos")
    fila = page.locator("tr", has_text="/m/ejemplo")
    fila.get_by_role("button", name="Deshabilitar").click()

    modal = page.locator("#modal-confirmar")
    expect(modal).to_be_visible()
    expect(modal).to_contain_text("Deshabilitar")
    modal.get_by_role("button", name="Cancelar").click()
    expect(modal).to_be_hidden()
    expect(fila).to_contain_text("Habilitado")


def test_aviso_de_sesion_por_vencer_y_extender(page: Page, servidor_aparte, errores_js):
    # Sesión de 1 minuto con aviso a los 55 s del final: el modal aparece a los ~5 s.
    srv = servidor_aparte(SESION_INACTIVIDAD_MINUTOS=1, SESION_AVISO_SEGUNDOS=55)
    entrar(page, srv.url, "qa_operador")
    modal = page.locator("#modal-sesion")
    expect(modal).to_be_visible(timeout=20_000)
    expect(modal).to_contain_text("Tu sesión está por vencer")
    modal.get_by_role("button", name=re.compile("Extender")).click()
    expect(modal).to_be_hidden()
