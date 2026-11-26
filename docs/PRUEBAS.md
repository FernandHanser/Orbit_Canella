# Pruebas automáticas

Las pruebas son programas que usan el hub como lo usaría una persona y comprueban que responda lo
correcto. Por ejemplo, que una contraseña incorrecta no deje entrar o que un usuario sin permiso
reciba "acceso denegado". Se corren todas juntas en unos segundos, **antes de publicar cualquier
cambio**: si todas pasan, lo que ya funcionaba sigue funcionando.

```bash
source .venv/Scripts/activate
python -m pytest                 # todas; al final debe decir "N passed"
python -m pytest -k ejecucion    # solo las que tienen "ejecucion" en el nombre
python -m pytest --co -q         # lista las pruebas sin correrlas
```

Requieren `requirements-dev.txt` instalado.

### Pruebas de punta a punta (navegador real)

`tests/e2e/` usa **Playwright** para abrir Chromium y usar el hub como una persona: ejecuta el
JavaScript real bajo la CSP, abre modales, mide pantallas en celular. Tardan más y necesitan un
navegador, así que **no** corren con `python -m pytest` ni en GitHub Actions: se piden a propósito.

```bash
pip install -r requirements-e2e.txt          # una vez
python -m playwright install chromium        # una vez (descarga ~120 MB)
python -m pytest --e2e tests/e2e             # todas las de punta a punta
python -m pytest --e2e tests/e2e --headed --slowmo 300   # viendo el navegador
```

Corren contra el **servidor de QA** (`tests/e2e/servidor.py`): el hub real con SQLite temporal,
STOD simulado, CSRF activo y **sin ninguna variable del `.env`**, así que ninguna pantalla puede
conectarse a SAP, Exchange o la base real. Usuarios sembrados (contraseña `Clave-QA-2026`):
`qa_super`, `qa_admin` (sin módulos), `qa_operador` (todos los módulos) y `qa_sin_modulos`.
Para recorrer el hub a mano sin la base real: `python -m tests.e2e.servidor` → http://127.0.0.1:5057.

Correrlas antes de subir cambios de interfaz (`templates/`, `static/`, `_macros.html`, `base.html`).
Para una revisión de QA completa (pruebas, reglas del hub y navegador, con informe), Claude Code
tiene el skill del proyecto **`qa-orbit`** (`.claude/skills/qa-orbit/`): basta pedir «haz QA de…».

---

## Tipos de prueba

| Tipo | Qué prueba | Ejemplos |
|---|---|---|
| **Integración** (la mayoría) | Varias piezas juntas, como las usaría una persona: un navegador simulado inicia sesión, entra a un módulo, ejecuta una tarea, y se revisan la base de datos y los logs | Acceso denegado aunque se escriba la URL; una tarea que falla deja su traza y revierte sus cambios |
| **Unitarias** | Una función aislada, sin base de datos ni servidor | Hash de contraseñas de STOD, saneamiento de logs, paginación |
| **Arquitectura** | No ejecutan el hub: leen el código (imports, textos, plantillas) y verifican las reglas de [ARQUITECTURA.md](ARQUITECTURA.md) | El núcleo no depende de los módulos; ningún módulo importa ni nombra a otro; no hay ciclos; cada módulo tiene sus pruebas |
| **Contrato de módulos** | Corren solas sobre **cada** módulo que el hub descubre, sin que nadie las escriba | Todas las rutas de un módulo (pantallas, API, estáticos) piden sesión, dan 403 sin el módulo asignado y 503 con el módulo deshabilitado |
| **De punta a punta** (`--e2e`) | Un navegador real (Playwright) contra el servidor de QA: lo que el `test_client` no ve porque no ejecuta JavaScript | El aviso de sesión aparece y «Extender» funciona; dar el rol de Administrador pide confirmación; en celular los botones no tapan el título |

Predominan las de integración porque lo que más interesa en el hub es que login, permisos, módulos,
base de datos y logs funcionen **juntos**. Una prueba unitaria no detectaría que alguien sin
permiso entra a un módulo escribiendo la URL.

## Qué cubren

| Archivo | Tema |
|---|---|
| [tests/test_acceso.py](../tests/test_acceso.py) | Inicio de sesión con STOD (contraseña incorrecta, inactivo, STOD caído, bloqueo por intentos, revalidación), permisos por módulo, administración de usuarios y roles, catálogo, CSRF y cabeceras de seguridad |
| [tests/test_logs_ejecuciones.py](../tests/test_logs_ejecuciones.py) | Logs (campos, filtros, saneamiento, sin contraseñas, sin ruido del servidor), ejecuciones (errores, tareas programadas, reversión de cambios, interrumpidas, sin cambios y su purga, ejecución exclusiva por módulo), consola y paginación |
| [tests/test_arquitectura.py](../tests/test_arquitectura.py) | Reglas de dependencias entre núcleo, integraciones y módulos; convivencia entre módulos ([principio 7](ARQUITECTURA.md#7-convivencia-entre-módulos)); que cada módulo tenga su `tests/test_<id>.py` |
| [tests/test_contrato_modulos.py](../tests/test_contrato_modulos.py) | Contrato de acceso de todo módulo: recorre todas sus rutas sin sesión, sin el módulo asignado (operador y administrador) y con el módulo deshabilitado |
| [tests/test_migraciones.py](../tests/test_migraciones.py) | Autogenerate nunca propone borrar las tablas de un módulo que no está cargado |
| [tests/test_scripts.py](../tests/test_scripts.py) | Scripts de despliegue: bien escritos y `despliegue.psd1` coherente (instala todos los `requirements-*.txt`). No los ejecuta |
| [tests/test_servidor.py](../tests/test_servidor.py) | Opciones de Waitress en `serve.py` detrás de un proxy (`PROXY_CONFIABLE`) |
| [tests/test_sesion.py](../tests/test_sesion.py) | Expiración de la sesión: inactividad, jornada, motivo, volver a la página, aviso, extender, API y formulario con sesión vencida (con CSRF activo) |
| [tests/test_interfaz.py](../tests/test_interfaz.py) | Tarjetas del inicio (última ejecución), spinners y confirmaciones en las pantallas clave (ver [INTERFAZ.md](INTERFAZ.md#spinners-y-confirmaciones)) |
| [tests/test_expedientes_seguros.py](../tests/test_expedientes_seguros.py) | Módulo Expedientes de Seguros: reglas, PDF, visor, paquete, correo, permisos y aseguradoras con SAP simulado (ver [PLAN_EXPEDIENTES_SEGUROS.md](PLAN_EXPEDIENTES_SEGUROS.md#pruebas)) |
| [tests/test_corte_caja.py](../tests/test_corte_caja.py) | Módulo Corte de caja: reglas, archivador, tarea con buzón simulado, panel y CLI (ver [PLAN_INTEGRACION_CORTE_DE_CAJA.md](PLAN_INTEGRACION_CORTE_DE_CAJA.md#pruebas)) |
| [tests/e2e/](../tests/e2e/) | De punta a punta con `--e2e`: login y ojo de contraseña, acceso a módulos, confirmación al deshabilitar un módulo y al dar el rol de Administrador, aviso de sesión, encabezados en celular. `servidor.py` es el servidor de QA |
| `tests/test_<id>.py` | Las de cada módulo, **obligatorio**: juego mínimo según lo que tenga el módulo en [AGREGAR_MODULO.md](AGREGAR_MODULO.md#9-pruebas) |

Los fixtures comunes (`app`, `client`, `entrar_como`, `crear_usuario`, `admin`, `autorizado`)
están en [tests/conftest.py](../tests/conftest.py).

## Qué no cubren

Las pruebas **no tocan nada real**: usan una base SQLite temporal en memoria y un STOD simulado
(`ProveedorSimulado`), que se borran al terminar. Por eso son rápidas y seguras, pero no detectan:

- **Diferencias propias de SQL Server.** Por ejemplo, índices filtrados, `SET` requeridos o
  intercalación. Los cambios de esquema se prueban además a mano en **SQL Server LocalDB** con una
  base desechable: `flask db upgrade`, `db check`, `db downgrade` y el script
  `scripts/sqlserver/02_esquema.sql` con `sqlcmd`. Ver
  [scripts/sqlserver/README.md](../scripts/sqlserver/README.md).
- **La conexión real a STOD**, a SAP, al correo o a carpetas compartidas. En las pruebas de un
  módulo, esas dependencias se simulan. La conexión real se verifica en el ambiente de desarrollo
  con datos de prueba.
- **La apariencia de las pantallas.** Se comprueba que rendericen y muestren el contenido, no
  cómo se ven. Eso se revisa en el navegador.

## Reglas

- `python -m pytest` pasa completo antes de publicar un cambio o un módulo.
- Cada corrección de un error lleva una prueba que lo reproduce, para que no vuelva.
- Si falla `test_arquitectura.py`, se corrige el diseño, no la prueba.
- Una prueba que falla no se borra ni se marca para omitir: se entiende por qué falla.
