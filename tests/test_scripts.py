"""Scripts de despliegue en scripts/ (docs/DESPLIEGUE.md, skill caddy-deploy).

No se ejecutan aquí, porque instalan servicios y tocan el firewall. Lo que sí se comprueba es lo
que rompería una instalación o una actualización sin que nadie lo note en el equipo: que los
archivos estén bien escritos y que despliegue.psd1 instale todo y sea coherente.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = sorted([*(RAIZ / "scripts").glob("*.ps1"), *(RAIZ / "scripts").glob("*.psd1")])
CONFIG = (RAIZ / "scripts" / "despliegue.psd1").read_text(encoding="utf-8-sig")
REQUISITOS = sorted(p.name for p in RAIZ.glob("requirements*.txt") if p.name != "requirements-dev.txt")


def _valor(clave: str) -> str:
    coincidencia = re.search(rf"^\s*{clave}\s*=\s*'?([^'\s]*)", CONFIG, re.MULTILINE)
    assert coincidencia, f"Falta {clave} en despliegue.psd1"
    return coincidencia.group(1)


def test_hay_scripts():
    assert {"actualizar.ps1", "instalar_pruebas.ps1", "despliegue.psd1"} <= {p.name for p in ARCHIVOS}


def test_instala_todos_los_requirements():
    """Un módulo nuevo con su requirements-<id>.txt debe agregarse también a despliegue.psd1."""
    faltan = [r for r in REQUISITOS if f"'{r}'" not in CONFIG]
    assert not faltan, f"despliegue.psd1 no instala: {faltan}"


def test_el_puerto_interno_lo_pone_el_instalador():
    """El puerto puede cambiar en el servidor (si está ocupado): no se fija en Env, lo pone EnvPuerto."""
    assert _valor("EnvPuerto") == "PORT"
    assert not re.search(r"^\s*PORT\s*=", CONFIG, re.MULTILINE)
    assert _valor("HOST") == "127.0.0.1"


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: p.name)
def test_powershell_sin_errores_de_sintaxis(archivo):
    powershell = shutil.which("powershell")
    if not powershell:
        pytest.skip("Sin Windows PowerShell en este equipo")
    analizar = (
        "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{archivo}', [ref]$null, [ref]$e); $e | ForEach-Object {{ $_.Message }}; exit $e.Count"
    )
    salida = subprocess.run([powershell, "-NoProfile", "-Command", analizar], capture_output=True, text=True)
    assert salida.returncode == 0, salida.stdout


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: p.name)
def test_con_bom_para_powershell_5(archivo):
    """Sin BOM, PowerShell 5.1 lee el archivo como ANSI y rompe los acentos de los mensajes."""
    assert archivo.read_bytes().startswith(b"\xef\xbb\xbf")
