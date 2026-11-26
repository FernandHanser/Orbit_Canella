# Playwright para Python en ORBIT

Guía práctica para escribir pruebas de punta a punta estables en este proyecto. Versión fijada en
`requirements-e2e.txt` (Playwright 1.65, pytest-playwright 0.10).

## Contenido
1. Cómo corren las pruebas aquí
2. Ubicar elementos (locators)
3. Esperar sin `sleep`: `expect`
4. Patrones del hub (login, modales, spinners, sesión, permisos)
5. Simular fallas con `page.route`
6. Varios usuarios a la vez
7. Depurar: headed, trace, codegen, capturas
8. Lo que vuelve frágil una prueba

---

## 1. Cómo corren las pruebas aquí

- Viven en `tests/e2e/` y **no** corren con `python -m pytest`: se piden con `--e2e`
  (`pytest_ignore_collect` en `tests/conftest.py`). GitHub Actions no las corre.
- El fixture `servidor` (alcance sesión) levanta el hub real en un puerto libre con
  `crear_app_qa()`: SQLite temporal, STOD simulado, CSRF activo y sin el `.env` real. Usuarios
  sembrados: `qa_super`, `qa_admin`, `qa_operador`, `qa_sin_modulos`; contraseña `CONTRASENA`.
  Ya traen nombres y apellidos, así que el formulario de usuario se puede guardar sin llenarlos.
- `servidor_aparte(**config)` crea otro servidor con configuración distinta (p. ej. sesión de un
  minuto). Úsalo en vez de tocar la configuración del compartido.
- `page` lo da pytest-playwright: un contexto nuevo por prueba (cookies limpias).
- `errores_js`: pídelo en toda prueba que abra pantallas; falla si hubo errores de JavaScript o
  violaciones de CSP. Una CSP rota (script en línea) solo se ve así.

```bash
python -m pytest --e2e tests/e2e                      # sin ventana
python -m pytest --e2e tests/e2e -k sesion --headed --slowmo 400   # viendo el navegador
python -m pytest --e2e tests/e2e --tracing retain-on-failure       # trace de las que fallan
```

## 2. Ubicar elementos (locators)

De más a menos preferido, porque los primeros siguen funcionando aunque cambie el HTML:

| Locator | Cuándo | Ejemplo |
|---|---|---|
| `get_by_role(rol, name=…)` | Botones, enlaces, encabezados, casillas | `page.get_by_role("button", name="Entrar")` |
| `get_by_label("…")` | Campos con `<label>` | `page.get_by_label("Correo de Cobros")` |
| `get_by_text("…")` | Mensajes y textos visibles | `page.get_by_text("Usuario o contraseña incorrectos.")` |
| `locator("#id")` | Campos de WTForms (el id es el nombre del campo) | `page.locator("#contrasena")` |
| `locator("[data-…]")` | Comportamientos del hub (`data-confirmar`, `data-sesion-*`) | `page.locator("[data-modal-aceptar]")` |
| `locator("tr", has_text=…)` | Una fila concreta de una tabla | `page.locator("tr", has_text="/m/ejemplo")` |

Encadena para acotar: `fila.get_by_role("button", name="Deshabilitar")`. Evita XPath y clases de
Tabler (`.btn-primary`): cambian con el diseño. Si un locator encuentra varios elementos, Playwright
falla en modo estricto; eso es bueno: acota en vez de usar `.first` a ciegas.

## 3. Esperar sin `sleep`: `expect`

Las acciones (`click`, `fill`) ya esperan a que el elemento esté visible y habilitado. Para
comprobar, usa `expect`, que reintenta hasta 5 s:

```python
from playwright.sync_api import expect
expect(page).to_have_url(re.compile(r"/m/ejemplo/$"))
expect(page.locator("#modal-confirmar")).to_be_visible()
expect(fila).to_contain_text("Habilitado")
expect(page.locator("#contrasena")).to_have_attribute("type", "text")
expect(modal).to_be_hidden()
expect(boton).to_be_disabled()            # p. ej. mientras corre data-cargando
```

Nunca `time.sleep()` ni `page.wait_for_timeout()` para «dar tiempo»: hacen la prueba lenta y aun
así frágil. Si algo tarda más (la cuenta de la sesión), sube el `timeout` de ese `expect` solamente.
El código HTTP de una navegación sale de `respuesta = page.goto(url)`; `respuesta.status`.

## 4. Patrones del hub

**Login.** `entrar(page, servidor.url, "qa_operador")` de `tests/e2e/conftest.py`. El error de
login es genérico a propósito («Usuario o contraseña incorrectos.»): comprueba ese texto exacto.

**Confirmaciones (`data-confirmar`).** El hub no usa `confirm()` del navegador: abre
`#modal-confirmar` (Tabler). Prueba los dos caminos: «Cancelar» no cambia nada y el botón de
confirmar (`[data-modal-aceptar]`) sí envía. Una acción destructiva o hacia terceros **sin** modal
es un hallazgo.

**Spinners (`data-cargando`).** Al enviar, el botón se deshabilita y cambia su texto. Para verlo
sin que la respuesta llegue antes, retrasa la petición con `page.route` (§5) y comprueba
`expect(boton).to_be_disabled()` y el texto del `data-cargando`.

**Aviso de sesión.** `servidor_aparte(SESION_INACTIVIDAD_MINUTOS=1, SESION_AVISO_SEGUNDOS=55)`:
el modal `#modal-sesion` aparece a los ~5 s. Ver `test_aviso_de_sesion_por_vencer_y_extender`.

**Permisos.** `qa_sin_modulos` debe recibir 403 con la página de error en español en cada ruta
del módulo; `qa_admin` no tiene módulos asignados (ser administrador no da acceso a módulos).
El contrato de acceso de todas las rutas ya lo prueba `tests/test_contrato_modulos.py`; en el
navegador interesa que **lo que ve la persona** sea claro.

**Celular.** `page.set_viewport_size({"width": 390, "height": 844})` y comprueba que no haya
desborde: `page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")` debe ser False.

## 5. Simular fallas con `page.route`

Intercepta peticiones para ver cómo responde la pantalla a errores, sin tocar sistemas reales:

```python
# La API del módulo responde 503 (p. ej. SAP caído): la pantalla debe avisar, no romperse.
page.route("**/m/<id>/api/**", lambda ruta: ruta.fulfill(
    status=503, content_type="application/json",
    body='{"error": "sap_no_disponible", "mensaje": "SAP no responde."}'))

# Respuesta lenta, para ver el spinner.
import time
page.route("**/admin/modulos/*/estado", lambda ruta: (time.sleep(1.5), ruta.continue_()))
```

`page.unroute(patron)` lo quita. Para fallas del lado del servidor (una tarea que lanza error),
mejor una prueba con `test_client` en `tests/test_<id>.py`, que es más rápida.

## 6. Varios usuarios a la vez

Cada usuario necesita su propio contexto (cookies separadas):

```python
def test_admin_deshabilita_y_el_operador_lo_ve(browser, servidor):
    admin = browser.new_context().new_page()
    operador = browser.new_context().new_page()
    entrar(admin, servidor.url, "qa_super")
    entrar(operador, servidor.url, "qa_operador")
    ...
```

Ojo: el servidor `servidor` es compartido por toda la sesión. Si una prueba **cambia estado**
(deshabilita un módulo, edita un usuario), usa `servidor_aparte()` o deja todo como estaba, para
no afectar a las siguientes.

## 7. Depurar

- `--headed --slowmo 400`: ver el navegador paso a paso.
- `page.pause()` dentro de la prueba (con `--headed`): abre el inspector y detiene ahí.
- `--tracing retain-on-failure` y luego `python -m playwright show-trace test-results/<…>/trace.zip`:
  línea de tiempo con capturas, red y consola de la prueba que falló. Es lo primero que se mira
  ante una prueba que falla «a veces».
- `python -m playwright codegen http://127.0.0.1:5057`: graba clics y propone locators (con
  `python -m tests.e2e.servidor` corriendo en otra terminal). Úsalo para descubrir locators, no
  pegues el código tal cual: reescríbelo con `expect` y los helpers del proyecto.
- `page.screenshot(path=…)` para evidencia en un informe. En escritorio, sin `full_page=True`: con página completa el menú lateral fijo se pinta encima del contenido y parece un defecto. En celular (390 px) sí conviene `full_page=True`.

## 8. Lo que vuelve frágil una prueba

| Síntoma | Causa | Corrección |
|---|---|---|
| Pasa en tu equipo y falla a veces | `sleep`, o comprobar antes de que termine el JS | `expect(...)` que reintenta |
| Falla tras un cambio de estilo | Locator por clase CSS o posición (`nth(2)`) | `get_by_role` / `get_by_text` / `data-*` |
| Una prueba rompe a la siguiente | Cambia estado en el servidor compartido | `servidor_aparte()` o restaurar |
| Falla solo con CSRF | Formulario o `fetch` sin token | Es un hallazgo real: el hub exige CSRF |
| «strict mode violation» | El locator encontró varios elementos | Acotar (`fila.get_by_role…`), no `.first` |
| Error de consola por un 403 esperado | El navegador registra toda respuesta ≥ 400 | Filtrar «Failed to load resource» si el 403 es el documento esperado |
