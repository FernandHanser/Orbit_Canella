"""Fixtures de las pruebas de punta a punta (Playwright).

Cada sesión de pruebas levanta un servidor de QA propio (``servidor.py``) en un puerto libre:
SQLite temporal, STOD simulado y sin nada del ``.env`` real. El navegador (fixture ``page`` de
pytest-playwright) entra por HTTP como lo haría una persona y ejecuta el JavaScript real
(``interaccion.js``, ``sesion.js``…), que es lo que las pruebas con ``test_client`` no ven.

Ver con el navegador a la vista: ``python -m pytest --e2e tests/e2e --headed --slowmo 300``.
"""
import re

import pytest
from playwright.sync_api import Page, expect

from .servidor import CONTRASENA, ServidorQA, crear_app_qa


@pytest.fixture(scope="session")
def servidor(tmp_path_factory):
    srv = ServidorQA(crear_app_qa(tmp_path_factory.mktemp("orbit-qa")), puerto=0).iniciar()
    yield srv
    srv.detener()


@pytest.fixture
def servidor_aparte(tmp_path):
    """Servidor propio con configuración distinta: ``servidor_aparte(SESION_AVISO_SEGUNDOS=…)``."""
    creados = []

    def _crear(**overrides):
        srv = ServidorQA(crear_app_qa(tmp_path / f"qa{len(creados)}", **overrides), puerto=0).iniciar()
        creados.append(srv)
        return srv

    yield _crear
    for srv in creados:
        srv.detener()


@pytest.fixture
def errores_js(page: Page):
    """Errores de JavaScript y de la CSP de la página. Una prueba que lo pide falla si hubo alguno."""
    errores: list[str] = []
    page.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
    page.on("console", lambda m: errores.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    yield errores
    assert not errores, "\n".join(errores)


def entrar(page: Page, url_base: str, usuario: str, contrasena: str = CONTRASENA) -> None:
    page.goto(f"{url_base}/acceso")
    page.locator("#usuario").fill(usuario)
    page.locator("#contrasena").fill(contrasena)
    page.get_by_role("button", name="Entrar").click()
    expect(page).not_to_have_url(re.compile(r"/acceso"))
