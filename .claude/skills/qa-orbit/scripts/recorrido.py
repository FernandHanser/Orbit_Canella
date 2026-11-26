"""Recorrido de QA: visita pantallas del hub con un usuario QA y deja evidencia.

Levanta el servidor de QA (tests/e2e/servidor.py: SQLite temporal, STOD simulado, sin el .env
real), entra con el usuario indicado y, por cada URL, registra el código HTTP, el título, los
errores de JavaScript y de la CSP, y capturas en escritorio (1366 px) y celular (390 px).

Uso, desde la raíz del repositorio y con el .venv activado:

    python .claude/skills/qa-orbit/scripts/recorrido.py --salida <carpeta> \
        --usuario qa_operador m/ejemplo/ m/expedientes_seguros/ admin/usuarios

Usuarios: qa_super, qa_admin, qa_operador, qa_sin_modulos (ver tests/e2e/servidor.py).
Deja en <carpeta>: recorrido.json, recorrido.md y capturas/*.png. Sale con 1 si alguna pantalla
dio 500, tuvo errores de JavaScript o algún recurso (CSS, JS, imagen) falló.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))

from playwright.sync_api import sync_playwright  # noqa: E402

from tests.e2e.servidor import CONTRASENA, ServidorQA, crear_app_qa  # noqa: E402

ANCHOS = {"escritorio": (1366, 900), "celular": (390, 844)}


def _nombre_archivo(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_") or "raiz"


def recorrer(urls: list[str], usuario: str, salida: Path, **config) -> list[dict]:
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "capturas").mkdir(exist_ok=True)
    srv = ServidorQA(crear_app_qa(salida / "_servidor", **config), puerto=0).iniciar()
    resultados = []
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            contexto = navegador.new_context(viewport=dict(zip(("width", "height"), ANCHOS["escritorio"])))
            page = contexto.new_page()
            errores: list[str] = []
            page.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
            # "Failed to load resource" lo escribe el navegador ante cualquier respuesta >= 400,
            # también la del propio documento (un 403 esperado): esos se registran aparte, por recurso.
            page.on("console", lambda m: errores.append(f"console.error: {m.text}")
                    if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
            recursos: list[str] = []
            page.on("response", lambda r: recursos.append(f"{r.status} {r.url.replace(srv.url, '')}")
                    if r.status >= 400 and r.request.resource_type != "document" else None)

            if usuario:
                page.goto(f"{srv.url}/acceso")
                page.locator("#usuario").fill(usuario)
                page.locator("#contrasena").fill(CONTRASENA)
                page.get_by_role("button", name="Entrar").click()
                page.wait_for_load_state("networkidle")
                if "/acceso" in page.url:
                    raise SystemExit(f"No se pudo entrar como {usuario!r}")

            for url in urls:
                errores.clear()
                recursos.clear()
                respuesta = page.goto(srv.url + url)
                page.wait_for_load_state("networkidle")
                capturas = {}
                for nombre, (ancho, alto) in ANCHOS.items():
                    page.set_viewport_size({"width": ancho, "height": alto})
                    archivo = salida / "capturas" / f"{_nombre_archivo(url)}_{nombre}.png"
                    # En escritorio, solo lo visible: en una captura de página completa el menú
                    # lateral fijo aparece encima del contenido, y parece un defecto que no existe.
                    page.screenshot(path=str(archivo), full_page=(nombre == "celular"))
                    capturas[nombre] = archivo.relative_to(salida).as_posix()
                page.set_viewport_size(dict(zip(("width", "height"), ANCHOS["escritorio"])))
                desborda = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                resultados.append({
                    "url": url,
                    "estado": respuesta.status if respuesta else None,
                    "url_final": page.url.replace(srv.url, ""),
                    "titulo": page.title(),
                    "errores_js": list(errores),
                    "recursos_con_error": list(recursos),
                    "desborde_horizontal_en_escritorio": desborda,
                    "capturas": capturas,
                })
            navegador.close()
    finally:
        srv.detener()
    return resultados


def _informe_md(resultados: list[dict], usuario: str) -> str:
    filas = [f"# Recorrido QA como `{usuario or 'sin sesión'}`", "",
             "| URL | Estado | Termina en | Errores JS | Recursos con error | Capturas |", "|---|---|---|---|---|---|"]
    for r in resultados:
        errores = "<br>".join(r["errores_js"]) or "—"
        recursos = "<br>".join(r["recursos_con_error"]) or "—"
        capturas = " · ".join(f"[{k}]({v})" for k, v in r["capturas"].items())
        filas.append(f"| `{r['url']}` | {r['estado']} | `{r['url_final']}` | {errores} | {recursos} | {capturas} |")
    return "\n".join(filas) + "\n"


def _ruta(texto: str) -> str:
    # Git Bash convierte "/m/x" en "C:/Program Files/Git/m/x": se acepta "m/x" (sin la barra) y se
    # detecta la conversión para no visitar una URL inválida.
    if re.match(r"^[A-Za-z]:[/\\]", texto):
        raise SystemExit(f"Git Bash convirtió la ruta en {texto!r}. Escríbela sin la barra inicial "
                         "(m/ejemplo/) o antepón MSYS_NO_PATHCONV=1 al comando.")
    return "/" + texto.lstrip("/")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("urls", nargs="+", type=_ruta, help="Rutas a visitar, p. ej. m/ejemplo/ (sin barra en Git Bash)")
    p.add_argument("--usuario", default="qa_operador", help="Usuario QA; vacío = sin sesión")
    p.add_argument("--salida", required=True, type=Path, help="Carpeta para el informe y las capturas")
    args = p.parse_args()

    resultados = recorrer(args.urls, args.usuario, args.salida)
    (args.salida / "recorrido.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.salida / "recorrido.md").write_text(_informe_md(resultados, args.usuario), encoding="utf-8")
    print(_informe_md(resultados, args.usuario))
    return 1 if any((r["estado"] or 0) >= 500 or r["errores_js"] or r["recursos_con_error"] for r in resultados) else 0


if __name__ == "__main__":
    raise SystemExit(main())
