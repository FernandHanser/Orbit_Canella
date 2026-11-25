"""Scripts de despliegue en scripts/*.ps1 (docs/DESPLIEGUE.md).

No se ejecutan aquí, porque instalan servicios y tocan el firewall. Lo que sí se comprueba es lo
que rompería una instalación o una actualización sin que nadie lo note en el equipo: que el
script esté bien escrito y que instale todos los requirements del hub.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((RAIZ / "scripts").glob("*.ps1"))
REQUISITOS = sorted(p.name for p in RAIZ.glob("requirements*.txt") if p.name != "requirements-dev.txt")


def test_hay_scripts():
    assert {"actualizar.ps1", "instalar_pruebas.ps1"} <= {p.name for p in SCRIPTS}


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_instala_todos_los_requirements(script):
    """Un módulo nuevo con su requirements-<id>.txt debe agregarse también a los scripts."""
    texto = script.read_text(encoding="utf-8-sig")
    faltan = [r for r in REQUISITOS if r not in texto]
    assert not faltan, f"{script.name} no instala: {faltan}"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_powershell_sin_errores_de_sintaxis(script):
    powershell = shutil.which("powershell")
    if not powershell:
        pytest.skip("Sin Windows PowerShell en este equipo")
    analizar = (
        "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{script}', [ref]$null, [ref]$e); $e | ForEach-Object {{ $_.Message }}; exit $e.Count"
    )
    salida = subprocess.run([powershell, "-NoProfile", "-Command", analizar], capture_output=True, text=True)
    assert salida.returncode == 0, salida.stdout


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_con_bom_para_powershell_5(script):
    """Sin BOM, PowerShell 5.1 lee el archivo como ANSI y rompe los acentos de los mensajes."""
    assert script.read_bytes().startswith(b"\xef\xbb\xbf")
