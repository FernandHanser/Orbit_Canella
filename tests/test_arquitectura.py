"""Reglas de dependencias del monolito modular, verificadas sobre los imports del código.

* El núcleo (``app/core``) no depende de ``app/integraciones`` ni de ``app/modulos``: las
  implementaciones concretas se conectan en ``create_app``.
* Un módulo no importa otro módulo ni los modelos ORM del núcleo (usa DTOs como
  ``ResumenEjecucion``).
* No hay ciclos de importación entre archivos de ``app/``.
* Las tablas llevan el prefijo de su dueño y las pantallas de un módulo usan una base del hub
  (``base.html`` o ``base_publica.html``).
* Convivencia: un módulo no nombra a otro (tablas, variables, tareas, rutas, carpetas), no
  registra ganchos que afecten a toda la aplicación y no modifica ``app.config`` ni ``os.environ``.
"""
import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app"


def _nombre(archivo: Path) -> str:
    partes = list(archivo.relative_to(RAIZ).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes.pop()
    return ".".join(partes)


def _imports() -> dict[str, set[str]]:
    """Módulo → módulos de ``app`` que importa (incluidos los imports dentro de funciones)."""
    grafo: dict[str, set[str]] = {}
    for archivo in APP.rglob("*.py"):
        nombre = _nombre(archivo)
        paquete = nombre if archivo.name == "__init__.py" else nombre.rpartition(".")[0]
        destinos = set()
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Import):
                destinos |= {a.name for a in nodo.names}
            elif isinstance(nodo, ast.ImportFrom):
                base = nodo.module or ""
                if nodo.level:
                    base = ".".join(paquete.split(".")[: len(paquete.split(".")) - nodo.level + 1] + ([base] if base else []))
                destinos.add(base)
        grafo[nombre] = {d for d in destinos if d == "app" or d.startswith("app.")}
    return grafo


def _resolver(destino: str, grafo: dict[str, set[str]]) -> str | None:
    while destino and destino not in grafo:
        destino = destino.rpartition(".")[0]
    return destino or None


def test_el_nucleo_no_depende_de_integraciones_ni_modulos():
    violaciones = [
        (origen, d) for origen, destinos in _imports().items() if origen.startswith("app.core")
        for d in destinos if d.startswith(("app.integraciones", "app.modulos"))
    ]
    assert not violaciones


def test_los_modulos_no_importan_otros_modulos_ni_modelos_del_nucleo():
    violaciones = []
    for origen, destinos in _imports().items():
        if not origen.startswith("app.modulos."):
            continue
        propio = ".".join(origen.split(".")[:3])
        for d in destinos:
            otro_modulo = d.startswith("app.modulos.") and not (d == propio or d.startswith(propio + "."))
            if otro_modulo or d.startswith("app.core.models"):
                violaciones.append((origen, d))
    assert not violaciones


def _carpetas_de_modulos() -> list[Path]:
    return sorted(p for p in (APP / "modulos").iterdir()
                  if p.is_dir() and not p.name.startswith("_") and (p / "__init__.py").exists())


def _textos(archivo: Path):
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            yield nodo.value


def _tablas(carpeta: Path) -> list[tuple[str, str]]:
    """(archivo, nombre) de cada ``__tablename__ = "..."`` declarado en la carpeta."""
    tablas = []
    for archivo in carpeta.rglob("*.py"):
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if (isinstance(nodo, ast.Assign) and any(getattr(t, "id", None) == "__tablename__" for t in nodo.targets)
                    and isinstance(nodo.value, ast.Constant)):
                tablas.append((archivo.name, nodo.value.value))
    return tablas


def test_las_tablas_llevan_el_prefijo_de_su_dueno():
    # Las tablas de un módulo se reconocen por el nombre en la base: así se respaldan, se
    # auditan o se retiran sin confundirlas con las de otro módulo ni con las del núcleo.
    violaciones = [("core", t) for _, t in _tablas(APP / "core") if not t.startswith("HUB_")]
    for carpeta in _carpetas_de_modulos():
        prefijo = carpeta.name.upper() + "_"
        violaciones += [(carpeta.name, t) for _, t in _tablas(carpeta) if not t.startswith(prefijo)]
    assert not violaciones


def test_los_modulos_no_nombran_tablas_del_nucleo():
    # Ni ForeignKey a HUB_USUARIOS ni SQL a mano contra HUB_*: el módulo guarda ``usuario_id`` o
    # ``ejecucion_id`` como enteros (principio 4), y así el núcleo cambia sus tablas sin romperlo.
    violaciones = [
        (str(archivo.relative_to(RAIZ)), texto)
        for carpeta in _carpetas_de_modulos() for archivo in carpeta.rglob("*.py")
        for texto in _textos(archivo) if "HUB_" in texto
    ]
    assert not violaciones


def test_las_plantillas_de_un_modulo_viven_en_templates_con_su_id():
    # Flask junta las carpetas templates de todos los Blueprints en un solo espacio de nombres:
    # dos módulos con "templates/inicio.html" se pisarían y ganaría el primero en cargarse.
    violaciones = []
    for carpeta in _carpetas_de_modulos():
        plantillas = carpeta / "templates"
        if plantillas.is_dir():
            violaciones += [(carpeta.name, p.name) for p in plantillas.iterdir() if p.name != carpeta.name]
    assert not violaciones


_EXTIENDE_BASE_DEL_HUB = re.compile(r"""\{%-?\s*extends\s+["'](base|base_publica)\.html["']""")
# Pantallas de un módulo que, a propósito, no usan una base del hub: "<módulo>/<archivo>": "motivo".
# Saltarse la regla es una decisión visible aquí, no un descuido.
EXCEPCIONES_PLANTILLAS: dict[str, str] = {}


def test_las_pantallas_de_un_modulo_usan_una_base_del_hub():
    # Con base.html la pantalla hereda menú, aviso de sesión, estilos, macros y mensajes; con
    # base_publica.html, la página sin sesión. Fuera de la regla, por convención de nombre: las
    # piezas que se incluyen en otra pantalla (_*.html) y los cuerpos de correo (correo_*.html).
    faltan = []
    for carpeta in _carpetas_de_modulos():
        for plantilla in sorted((carpeta / "templates").rglob("*.html")):
            nombre = plantilla.name
            clave = f"{carpeta.name}/{nombre}"
            if nombre.startswith(("_", "correo_")) or clave in EXCEPCIONES_PLANTILLAS:
                continue
            if not _EXTIENDE_BASE_DEL_HUB.search(plantilla.read_text(encoding="utf-8")):
                faltan.append(clave)
    assert not faltan, (
        "Estas pantallas no extienden una base del hub: " + ", ".join(faltan) + ". Agrega "
        '{% extends "base.html" %} (o "base_publica.html" si es sin sesión). Si es una pieza que se '
        "incluye en otra pantalla, nómbrala con «_»; si es el cuerpo de un correo, con «correo_». "
        "Ver docs/AGREGAR_MODULO.md#5-plantillas."
    )


# ---------------------------------------------------------------- convivencia entre módulos

def _id_declarado(carpeta: Path) -> str | None:
    """Valor de ``id=`` en la llamada ``DefinicionModulo(...)`` del ``__init__.py`` del módulo."""
    for nodo in ast.walk(ast.parse((carpeta / "__init__.py").read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) == "DefinicionModulo":
            for k in nodo.keywords:
                if k.arg == "id" and isinstance(k.value, ast.Constant):
                    return k.value.value
    return None


def test_la_carpeta_de_un_modulo_se_llama_como_su_id():
    # Las demás reglas (prefijo de tablas, templates/<id>/, referencias a otros módulos) se
    # calculan con el nombre de la carpeta: si no coincide con el id, dejarían de proteger.
    distintas = [(c.name, _id_declarado(c)) for c in _carpetas_de_modulos() if _id_declarado(c) != c.name]
    assert not distintas


_REFERENCIA_EN_PLANTILLA = r"""url_for\(\s*["']{id}\.|/m/{id}\b|\b{ID}_"""


def test_un_modulo_no_nombra_a_otro_modulo():
    # Además de no importarlo: un módulo no lee las tablas de otro con SQL a mano (CORTE_CAJA_*),
    # no usa sus variables de .env, no lanza sus tareas (ejecutar_tarea("otro", ...)), no enlaza
    # sus pantallas (url_for("otro.x"), /m/otro) ni escribe en su carpeta (instance/otro).
    # Si dos módulos necesitan hablarse, es con un evento del núcleo (ARQUITECTURA.md, principio 6).
    carpetas = _carpetas_de_modulos()
    violaciones = []
    for carpeta in carpetas:
        for otro in (c.name for c in carpetas if c != carpeta):
            for archivo in carpeta.rglob("*.py"):
                violaciones += [
                    (str(archivo.relative_to(RAIZ)), t) for t in _textos(archivo)
                    if t == otro or t.startswith(otro + ".") or f"/m/{otro}" in t or f"{otro.upper()}_" in t
                ]
            patron = re.compile(_REFERENCIA_EN_PLANTILLA.format(id=otro, ID=otro.upper()))
            for archivo in (p for p in carpeta.rglob("*") if p.suffix in {".html", ".js", ".css"}):
                if patron.search(archivo.read_text(encoding="utf-8")):
                    violaciones.append((str(archivo.relative_to(RAIZ)), otro))
    assert not violaciones


# Métodos de Blueprint que actúan sobre TODA la aplicación, no solo sobre las rutas del módulo.
_GANCHOS_GLOBALES = {
    "before_app_request", "after_app_request", "teardown_app_request", "app_context_processor",
    "app_errorhandler", "app_template_filter", "app_template_global", "app_template_test",
    "app_url_defaults", "app_url_value_preprocessor", "add_app_template_filter",
    "add_app_template_global", "add_app_template_test",
}
# Ganchos globales permitidos a propósito: "<módulo>/<archivo>:<gancho>": "motivo".
EXCEPCIONES_GANCHOS: dict[str, str] = {}


def test_los_modulos_no_registran_ganchos_globales():
    # Un before_app_request de un módulo corre en cada petición del hub y de los demás módulos;
    # un app_errorhandler reemplaza las páginas de error de todos. Lo común es del núcleo.
    violaciones = []
    for carpeta in _carpetas_de_modulos():
        for archivo in carpeta.rglob("*.py"):
            for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
                if isinstance(nodo, ast.Attribute) and nodo.attr in _GANCHOS_GLOBALES:
                    clave = f"{carpeta.name}/{archivo.name}:{nodo.attr}"
                    if clave not in EXCEPCIONES_GANCHOS:
                        violaciones.append(clave)
    assert not violaciones, (
        "Estos módulos registran ganchos que afectan a todo el hub: " + ", ".join(violaciones)
        + ". Usa la versión del Blueprint (before_request, context_processor, errorhandler…), que "
        "solo aplica a las rutas del módulo. Ver docs/ARQUITECTURA.md#7-convivencia-entre-módulos."
    )


def _modifica_configuracion_comun(nodo: ast.AST) -> bool:
    """``os.environ[...] = …``, ``app.config[...] = …``, ``os.environ.update(…)``, ``config.setdefault(…)``…"""
    def es_comun(expr) -> bool:
        return isinstance(expr, ast.Attribute) and expr.attr in {"environ", "config"}

    if isinstance(nodo, (ast.Assign, ast.AugAssign, ast.Delete)):
        objetivos = nodo.targets if isinstance(nodo, (ast.Assign, ast.Delete)) else [nodo.target]
        return any(isinstance(t, ast.Subscript) and es_comun(t.value) for t in objetivos)
    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute):
        return nodo.func.attr in {"update", "setdefault", "pop", "clear", "__setitem__"} and es_comun(nodo.func.value)
    return False


def test_los_modulos_no_modifican_la_configuracion_comun():
    # app.config y os.environ los leen el núcleo y todos los módulos: si uno los cambia en tiempo
    # de ejecución, el comportamiento de otro depende del orden en que se cargaron.
    violaciones = [
        f"{archivo.relative_to(RAIZ)}:{nodo.lineno}"
        for carpeta in _carpetas_de_modulos() for archivo in carpeta.rglob("*.py")
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8")))
        if _modifica_configuracion_comun(nodo)
    ]
    assert not violaciones


# Módulos cuyas pruebas viven en otro archivo a propósito: "<id>": "motivo".
EXCEPCIONES_PRUEBAS: dict[str, str] = {
    "ejemplo": "plantilla de referencia; sus rutas y su tarea se prueban en test_acceso.py y "
               "test_logs_ejecuciones.py, porque son las que usan las pruebas del núcleo",
}


def test_cada_modulo_tiene_sus_pruebas():
    # El contrato común (test_contrato_modulos.py) solo cubre el acceso. Lo propio del módulo
    # (reglas, tareas, sistemas externos simulados) va en tests/test_<id>.py: ver
    # docs/AGREGAR_MODULO.md#9-pruebas.
    sin_pruebas = [c.name for c in _carpetas_de_modulos()
                   if c.name not in EXCEPCIONES_PRUEBAS and not (RAIZ / "tests" / f"test_{c.name}.py").exists()]
    assert not sin_pruebas, (
        "Módulos sin tests/test_<id>.py: " + ", ".join(sin_pruebas)
        + ". Ver docs/AGREGAR_MODULO.md#9-pruebas (juego mínimo por módulo)."
    )


def test_sin_ciclos_de_importacion():
    grafo = _imports()
    aristas = {o: {r for d in ds if (r := _resolver(d, grafo)) and r != o} for o, ds in grafo.items()}
    # Un paquete importado por sus propios submódulos (``from . import x``) no cuenta como ciclo.
    aristas = {o: {d for d in ds if not o.startswith(d + ".")} for o, ds in aristas.items()}

    visitando, terminados, ciclos = set(), set(), []

    def visitar(nodo, camino):
        visitando.add(nodo)
        for sig in aristas.get(nodo, ()):
            if sig in visitando:
                ciclos.append(camino[camino.index(sig):] + [sig])
            elif sig not in terminados:
                visitar(sig, camino + [sig])
        visitando.discard(nodo)
        terminados.add(nodo)

    for nodo in sorted(aristas):
        if nodo not in terminados:
            visitar(nodo, [nodo])
    assert not ciclos, ciclos
