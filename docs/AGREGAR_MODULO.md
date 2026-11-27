# Agregar un módulo

Un módulo es una carpeta en `app/modulos/<id>/` que expone `MODULO = DefinicionModulo(...)`.
Al arrancar, el hub la descubre, monta su Blueprint en `/m/<id>`, la agrega al catálogo y protege
**todas** sus rutas (web, API y estáticos). No hay que tocar el núcleo ni otros módulos.

Referencia completa y funcionando: [`app/modulos/ejemplo/`](../app/modulos/ejemplo/).

---

## 1. Estructura

```text
app/modulos/conciliacion/
├── __init__.py          # MODULO = DefinicionModulo(...)  (obligatorio)
├── views.py             # Blueprint raíz: pantallas
├── api.py               # (opcional) Blueprint anidado: /m/conciliacion/api/...
├── services.py          # lógica contable e integraciones, sin dependencia de Flask
├── models.py            # (opcional) tablas propias
├── templates/conciliacion/inicio.html
└── static/              # (opcional) JS/CSS/imágenes propios
```

Las plantillas van en `templates/<id>/` (con la subcarpeta del id) para no chocar con las de
otros módulos ni del hub.

---

## 2. Identificador

- Minúsculas, números y `_`; empieza con letra; entre 2 y 64 caracteres (`conciliacion`,
  `corte_caja`).
- Reservados: `core`, `admin`, `auth`, `hub`, `static`, `api`, `sistema`.
- Es el mismo valor en: nombre de la carpeta, `DefinicionModulo(id=...)`, nombre del Blueprint
  y `get_logger("<id>")`. **No se cambia** después de publicado: los permisos y los logs se
  guardan con él.

---

## 3. Blueprint y definición

```python
# views.py
from flask import Blueprint, render_template
from app.core.logs import get_logger

bp = Blueprint(
    "conciliacion", __name__,                 # nombre == id del módulo (se valida al arrancar)
    template_folder="templates",
    static_folder="static", static_url_path="/static",   # solo si el módulo tiene static/
)
log = get_logger("conciliacion")

@bp.route("/")
def inicio():
    return render_template("conciliacion/inicio.html")
```

```python
# __init__.py
from app.core.registro import DefinicionModulo

from . import api            # si existe: registra el Blueprint anidado
from . import models         # si existe: registra las tablas para las migraciones
from .services import conciliar
from .views import bp

MODULO = DefinicionModulo(
    id="conciliacion",
    nombre="Conciliación bancaria",                       # tarjeta y menú
    descripcion="Concilia estados de cuenta contra SAP.",  # tarjeta del inicio
    icono="building-bank",             # nombre de Tabler Icons sin "ti-" (https://tabler.io/icons)
    blueprint=bp,
    vista_inicio="inicio",             # función de views.py a la que llevan la tarjeta y el menú
    tareas={"conciliar": conciliar},   # opcional: ejecutables sin sesión web
    version="1.0.0",
)
```

Opcionales: `ruta` (por defecto `/m/<id>`), `permiso` (por defecto `modulo.<id>`),
`es_ejemplo` (muestra la etiqueta "Ejemplo").

**Descripción:** una línea con lo que hace el módulo, en verbos ("Archiva los cortes que llegan
por correo y rechaza los que no cumplen"). La explicación larga va dentro del módulo. Su tarjeta del inicio
muestra además la última ejecución, sin que el módulo haga nada.



---

## 4. API

Registra la API como Blueprint **anidado** dentro del Blueprint del módulo para heredar la
protección:

```python
# api.py
from flask import Blueprint, jsonify
from .views import bp as bp_modulo

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.get("/estado")
def estado():
    return jsonify(ok=True)

bp_modulo.register_blueprint(api_bp)      # → /m/conciliacion/api/estado
```

Respuestas automáticas del núcleo, en JSON: sin sesión `401`, sin permiso `403`, módulo
deshabilitado `503`, ruta inexistente `404`. Las peticiones que modifican datos deben enviar la
cabecera `X-CSRFToken` con el valor de `csrf_token()`.

---

## 5. Plantillas

```jinja
{% extends "base.html" %}
{% from "_macros.html" import encabezado, estado_ejecucion, paginacion as pie_paginacion %}
{% block titulo %}Conciliación bancaria{% endblock %}
{% block encabezado %}{{ encabezado("Conciliación bancaria", "Automatizaciones") }}{% endblock %}
{% block contenido %}
  <div class="card"> ... </div>
{% endblock %}
```

- **Toda pantalla del módulo extiende `base.html`** (o `base_publica.html` si es sin sesión): así
  hereda el menú, el aviso de sesión, los estilos, las macros y los mensajes sin hacer nada más.
  Quedan fuera, por su nombre, las piezas que se incluyen en otra pantalla (`_checklist.html`) y
  los cuerpos de correo (`correo_rechazo.html`). Lo verifica
  `tests/test_arquitectura.py::test_las_pantallas_de_un_modulo_usan_una_base_del_hub`; una
  excepción de verdad (p. ej. una vista de impresión) se declara en `EXCEPCIONES_PLANTILLAS` de esa
  prueba, con el motivo.
- Bloques disponibles: `titulo`, `encabezado`, `contenido`, `head`, `scripts` y `modales`.
- Formularios POST: incluir `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
  o usar un `FlaskForm` con `{{ form.hidden_tag() }}`.
- Macros, estilos y reglas de la CSP: ver [INTERFAZ.md](INTERFAZ.md).
- Botones que ejecutan algo: `data-cargando` (spinner) y, si hay efectos irreversibles,
  `data-confirmar` (modal). Ver [INTERFAZ.md](INTERFAZ.md#spinners-y-confirmaciones).
- Tablas: la columna de acciones con `col-acciones` (queda fija a la derecha) y, si cada fila
  abre un detalle, `data-fila-enlace` en el `<tr>` más un enlace normal en la fila. Ver
  [INTERFAZ.md](INTERFAZ.md#tablas-reglas-de-la-plantilla-del-hub).

### Listas largas: paginación

```python
# views.py
from app.core.paginacion import POR_PAGINA, pagina_actual

@bp.route("/partidas")
def partidas():
    pagina = Partida.query.order_by(Partida.fecha.desc()).paginate(
        page=pagina_actual(), per_page=POR_PAGINA, error_out=False)
    return render_template("conciliacion/partidas.html", partidas=pagina.items, pagina=pagina)
```

```jinja
{# importar la macro con alias para que no choque con variables llamadas "paginacion" #}
{% from "_macros.html" import paginacion as pie_paginacion %}
<div class="card">
  <table class="table card-table"> {% for p in partidas %} ... {% endfor %} </table>
  {{ pie_paginacion(pagina, "partidas") }}
</div>
```

Los filtros de la URL se conservan al cambiar de página. Para listas ya cargadas en memoria:
`PaginaLista(lista, pagina_actual(), POR_PAGINA)`. `POR_PAGINA` (15) es el tamaño de página de todo el hub: no
fijes otro número en el módulo.

---

## 6. Archivos estáticos del módulo

Con `static_folder="static", static_url_path="/static"` en el Blueprint, los archivos de
`app/modulos/<id>/static/` se sirven en `/m/<id>/static/...` y también exigen permiso del módulo.

```jinja
{% block scripts %}
<script src="{{ url_for('conciliacion.static', filename='conciliacion.js') }}"></script>
{% endblock %}
```

La CSP no permite JavaScript inline (`<script>...</script>` ni `onclick="..."`): todo el JS va
en archivos. Para archivos del hub (`app/static/`) usa `estatico('ruta')`, ver [INTERFAZ.md](INTERFAZ.md).

Un modal propio del módulo (por ejemplo, un visor a pantalla completa) va en `{% block modales %}`,
no en `{% block contenido %}`: ese bloque vive fuera de `.container-xl`, igual que los modales
compartidos del hub (`#modal-sesion`, `#modal-confirmar`). Un modal que se queda dentro de
`contenido` no llena el alto de la ventana y su pie (botones, navegación) termina fuera de la
vista — así se rompió el visor de Expedientes de Seguros (corregido el 29/09/2026).

```jinja
{% block modales %}
<div class="modal modal-blur fade" id="mi-modal" tabindex="-1" aria-hidden="true">...</div>
{% endblock %}
```

---

## 7. Tablas propias

```python
# models.py
from app.extensions import db

class Partida(db.Model):
    __tablename__ = "CONCILIACION_PARTIDAS"      # prefijo <ID_MODULO>_ en mayúsculas, obligatorio
    id = db.Column(db.Integer, primary_key=True)
    ...
```

1. Importa `models` en el `__init__.py` del módulo (si no, Alembic no ve las tablas).
2. `flask --app wsgi db migrate -m "conciliacion: tablas"` y revisa el archivo generado en
   `migrations/versions/`.
3. `flask --app wsgi db upgrade`.
4. Regenera `scripts/sqlserver/02_esquema.sql` con `python scripts/sqlserver/generar_esquema.py`.

**Datos iniciales** (catálogos que el módulo necesita para funcionar): decláralos en la migración
como `DATOS_INICIALES = {"TABLA": [ {...}, ... ]}` y siémbralos con
`op.bulk_insert(tabla, DATOS_INICIALES["TABLA"])`. El generador de `02_esquema.sql` los lee de ahí,
así hay una sola fuente. Ejemplo: `migrations/versions/b5d844416447_corte_caja_tablas_y_empresas.py`.
Si una fila depende de otra (una llave foránea que se busca por nombre), va como SQL simple en
`SQL_INICIAL = ["INSERT ... SELECT ..."]`, que la migración ejecuta con `op.execute` y el generador
también incluye. Ejemplo: `d03cd8372eae_expedientes_seguros_tablas.py`.

La base productiva es SQL Server: filtra booleanos con `columna == True` (no `.is_(True)`) y no
pongas dos llaves foráneas con cascada hacia la misma tabla (ver
[scripts/sqlserver/README.md](../scripts/sqlserver/README.md)).

No modifiques tablas del núcleo (prefijo `HUB_`: `HUB_USUARIOS`, `HUB_MODULOS`, `HUB_PERMISOS_MODULO`,
`HUB_EJECUCIONES`, `HUB_INTENTOS_ACCESO`). Para
relacionar registros con quien los creó, guarda el `ejecucion_id` o el `usuario_id` como entero,
sin `ForeignKey` hacia `HUB_*`. El prefijo, esta regla y la carpeta `templates/<id>/` las verifica
`tests/test_arquitectura.py`.

### Las migraciones nunca borran tablas que no conocen

Todos los módulos comparten una sola cadena de Alembic. `flask db migrate` compara la base con los
modelos **cargados**: si generas una migración con `AUTOMATE_MODULOS` limitado, o un módulo falló
al importarse, sus tablas no aparecen en los modelos. Por eso el hub instala un filtro
(`app/core/migraciones.py`) que ignora toda tabla que está en la base y no en los modelos:
autogenerate **nunca propone un `DROP TABLE`**. Sí sigue detectando tablas nuevas y cambios de
columnas en las tablas de los módulos cargados.

Aun así, antes de `db upgrade` revisa el archivo generado y confirma que solo toca tablas de tu
módulo. Si dos personas generan migraciones al mismo tiempo, quedan dos «heads»: se unen con
`flask --app wsgi db merge heads -m "unir ramas"`.

### Retirar un módulo con tablas

1. Deshabilítalo en el catálogo (sus rutas y tareas se detienen; los datos quedan).
2. Respalda sus tablas (`<ID_MODULO>_*`) si hay que conservar el histórico.
3. Escribe a mano una migración con `op.drop_table("<ID_MODULO>_...")` por cada tabla (hijas
   primero) y un `downgrade` que las recree. Autogenerate no la va a proponer: es a propósito.
4. Aplica la migración y, después, borra la carpeta del módulo. El catálogo lo marca «sin código».

---

## 8. Logs y ejecuciones

- Usa siempre `get_logger("<id>")`; no configures handlers, archivos ni `print`. Ver [LOGS.md](LOGS.md).
- Toda corrida de una automatización pasa por `ejecucion(...)` o `ejecutar_tarea(...)` para
  quedar registrada y vinculada a sus logs. Ver [EJECUCIONES.md](EJECUCIONES.md).
- Para mostrar corridas usa `ultimas_ejecuciones(...)`: devuelve `ResumenEjecucion`, no filas ORM.
  Pero piensa en el actor: el panel de un módulo muestra **datos del negocio** (qué se procesó,
  qué se rechazó). Las ejecuciones con sus errores técnicos ya están en **Administración →
  Ejecuciones** y el estado del robot en la tarjeta del inicio; no las repitas en el panel salvo
  que el operador pueda actuar sobre ellas.
- Un módulo corre **una ejecución a la vez**: atrapa `EjecucionEnCurso` para avisar al usuario
  (pantalla) o responder 409 (API). Ver [EJECUCIONES.md](EJECUCIONES.md#ejecución-exclusiva-por-módulo).
- Dentro de una tarea **no llames a `db.session.commit()`**: `ejecucion()` confirma tus cambios
  junto con el estado final, o los revierte si la tarea falla. Los efectos externos (correo,
  archivos, SAP) van al final y deben poder repetirse sin duplicarse. Ver
  [ARQUITECTURA.md](ARQUITECTURA.md#atomicidad).
- Tarea por lotes: aísla cada elemento (regla 5 de atomicidad). Tarea programada que no encontró
  nada: `ctx.estado = "sin_cambios"` ([EJECUCIONES.md](EJECUCIONES.md#corridas-sin-cambios)).

---

## 8b. Comandos de consola, dependencias y configuración

- **Comandos propios**: con `@bp.cli.command("nombre")` quedan como
  `flask --app wsgi <id> nombre`, sin tocar el núcleo. Ejemplo: `app/modulos/corte_caja/cli.py`.
- **Dependencias externas**: en `requirements-<id>.txt`, importadas **dentro** del adaptador que
  las usa (no al importar el módulo), para que el hub y las pruebas carguen el módulo sin ellas.
- **Configuración**: variables `<ID>_*` leídas al ejecutar la tarea, no al importar: si faltan,
  el hub arranca igual y la ejecución falla con la lista de las que faltan.
- **Sistemas externos** (buzón, SAP, carpetas): un contrato (`Protocol`) en el módulo y un
  adaptador real; en las pruebas, un doble que lo implementa. Ejemplo: `Buzon` / `BuzonEws` /
  `BuzonFalso`.
- **Modo simulación** cuando la tarea tenga efectos hacia terceros (responder correos, escribir
  en SAP): permite probar contra el sistema real sin afectarlo.

## 9. Pruebas

Crea `tests/test_<id>.py` usando los fixtures de `tests/conftest.py` (`app`, `client`,
`entrar_como`, `crear_usuario`). Las pruebas usan un STOD simulado: `crear_usuario` registra al
usuario en él y en el hub.

```python
from .conftest import crear_usuario

def test_con_permiso(entrar_como, app):
    u = crear_usuario("con_permiso", modulos=["conciliacion"])
    assert entrar_como(u).get("/m/conciliacion/").status_code == 200

def test_sin_permiso(entrar_como, app):
    u = crear_usuario("sin_permiso")
    assert entrar_como(u).get("/m/conciliacion/").status_code == 403
```

### Lo que ya está probado sin que escribas nada

`tests/test_contrato_modulos.py` recorre **todas** las rutas de cada módulo que el hub descubre
(pantallas, API y estáticos) y verifica que sin sesión no respondan, que sin el módulo asignado
den 403 (también a un administrador) y que con el módulo deshabilitado den 503. Además,
`tests/test_arquitectura.py` exige que exista `tests/test_<id>.py` y verifica las reglas de
convivencia ([ARQUITECTURA.md, principio 7](ARQUITECTURA.md#7-convivencia-entre-módulos)).

### Juego de pruebas del módulo (`tests/test_<id>.py`)

Va **completo antes de publicar el módulo**. Cada fila aplica si el módulo tiene esa pieza; la
columna «Ejemplo» es una prueba real que puedes copiar.

| Si el módulo tiene… | Prueba como mínimo | Ejemplo |
|---|---|---|
| Pantallas | Con el módulo asignado, la pantalla de inicio responde 200 y muestra su contenido | `test_tablero_con_y_sin_permiso` (corte_caja) |
| Reglas de negocio (`reglas.py`) | Cada regla con casos válidos, inválidos y límite, sin base ni red (unitarias) | `test_rangos_y_paginas_elegidas` (expedientes) |
| Acciones solo para administradores | Un operador con el módulo recibe 403 en **cada** una (GET y POST) | `test_aseguradoras_solo_administradores` (expedientes) |
| Sistemas externos (SAP, buzón, SMTP, carpetas) | Siempre con un doble del contrato (`Protocol`), nunca contra el real. Que el sistema caído dé un mensaje claro o un 503, no un error 500 | `test_miniatura_con_sap_caido_da_503` (expedientes) |
| Variables `<ID>_*` en `.env` | Si falta una, el error nombra exactamente cuál falta, y la pantalla avisa sin intentar conectarse | `test_modulo_sin_configurar_avisa_en_bandeja_y_en_visor` (expedientes) |
| Tareas | Corrida exitosa (estado y `ctx.resultado`) y, si la tarea falla a mitad, **sus filas se revierten** | `test_fallo_de_la_corrida_revierte_filas` (corte_caja) |
| Tareas por lotes | Un elemento malo queda con estado `error`, los demás se procesan y la corrida termina en `advertencia`; sin nada que hacer, `sin_cambios` | `test_un_correo_con_error_no_detiene_a_los_demas` (corte_caja) |
| Efectos externos (correo, archivos, SAP) | Repetir la acción no duplica el efecto (doble clic, tarea repetida) | `test_si_no_se_puede_mover_se_reintenta_sin_duplicar_archivos` (corte_caja) |
| Modo simulación o prueba | En ese modo no sale nada hacia terceros | — (corte_caja lo tuvo hasta el 27/11/2026) |
| Comandos de consola | Cada comando con un caso que funciona y uno que falla (código de salida ≠ 0) | `test_cli_empresas` (corte_caja) |
| Listados | Paginación, y que el número de consultas no crezca con las filas (`contar_consultas`) | `test_lista_de_aseguradoras_sin_n_mas_1` (expedientes) |
| Archivos con datos personales | No quedan archivos sueltos si algo falla a medias | `test_si_falla_un_archivo_aparte_no_queda_nada_a_medias` (expedientes) |

Reglas: ninguna prueba se conecta a SAP, a correo ni a carpetas reales; cada error corregido
lleva su prueba. Tipos de prueba, qué cubren y qué no: [PRUEBAS.md](PRUEBAS.md).

---

## 9b. Acciones solo para administradores

El núcleo ya exige el permiso del módulo en todas sus rutas. Si dentro del módulo hay acciones
de configuración (por ejemplo, el CRUD de una tabla de parámetros), restríngelas a los
administradores del hub con el contrato de `app/core/permisos.py`:

```python
from app.core.permisos import es_administrador, solo_administradores

@bp.route("/empresas/nueva", methods=["GET", "POST"])
@solo_administradores                        # 403 para quien no es admin/superadmin
def empresa_nueva(): ...

render_template("...", puede_editar=es_administrador())   # para mostrar u ocultar botones
```

Ejemplo: `app/modulos/expedientes_seguros/aseguradoras.py`.

## 10. No hagas

- Decoradores de login o permisos propios, o leer `current_user.rol`: el núcleo ya verifica cada
  petición y ofrece `app/core/permisos.py`.
- Credenciales con valores por defecto en el código: usa variables de entorno **sin default**
  (`os.environ["CONCILIACION_SAP_USER"]`) y documéntalas en `.env.example` sin valores reales.
- Hilos en segundo plano al importar el módulo: declara tareas y prográmalas
  ([EJECUCIONES.md](EJECUCIONES.md)).
- `debug=True`, `app.run()` o un `create_app()` propio: el módulo corre dentro del hub.
- Importar otro módulo (`app.modulos.<otro>`) o los modelos del núcleo (`app.core.models`):
  usa los servicios públicos del núcleo. `tests/test_arquitectura.py` lo verifica. Ver
  [ARQUITECTURA.md](ARQUITECTURA.md).
- Nombrar a otro módulo aunque no lo importes: SQL contra sus tablas, sus variables `.env`,
  `ejecutar_tarea("otro", ...)`, `url_for("otro.x")`, `/m/otro` o `instance/otro`.
- Cambiar `ruta=` o `permiso=` en `DefinicionModulo`: el módulo vive en `/m/<id>` (el hub se niega
  a arrancarlo si no).
- Ganchos de toda la aplicación (`before_app_request`, `app_errorhandler`,
  `app_context_processor`, `app_template_filter`…): usa la versión del Blueprint, que solo aplica
  a tus rutas. Ni modificar `app.config` u `os.environ`.

Todas estas reglas las verifica `python -m pytest`; lista y motivos en
[ARQUITECTURA.md, principio 7](ARQUITECTURA.md#7-convivencia-entre-módulos).

---

## 11. Lista de verificación para publicar

- [ ] La carpeta, el `id`, el Blueprint y `get_logger` usan el mismo identificador.
- [ ] `tests/test_<id>.py` cubre cada fila que aplica del [juego de pruebas](#juego-de-pruebas-del-módulo-teststest_idpy).
- [ ] `python -m pytest` pasa, incluidas las pruebas del módulo, las de arquitectura y el contrato de módulos.
- [ ] Revisado en navegador contra el servidor de QA: `python -m pytest --e2e tests/e2e` pasa y sus
      pantallas se ven bien en escritorio y celular. Con Claude Code: «haz QA del módulo <id>» (skill
      `qa-orbit`, que entrega un informe con veredicto). Ver [PRUEBAS.md](PRUEBAS.md#pruebas-de-punta-a-punta-navegador-real).
- [ ] Migración generada, revisada y aplicada (si hay tablas).
- [ ] Variables nuevas agregadas a `.env.example` sin valores reales.
- [ ] Reiniciado el servidor: el módulo aparece en **Catálogo de módulos**, habilitado y sin
      usuarios (o `flask --app wsgi modulos sincronizar`).
- [ ] Asignado a las personas en **Usuarios y permisos**.
- [ ] Sección del módulo en [GLOSARIO.md](GLOSARIO.md): actores reales, qué puede cada uno y términos del negocio.

Para retirar un módulo: deshabilítalo en el catálogo (bloquea sus rutas sin borrar
asignaciones) y luego elimina su carpeta.
