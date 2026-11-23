<#
.SYNOPSIS
    Actualiza el hub en un servidor a lo último de su rama en GitHub (main en producción, dev en pruebas).

.DESCRIPTION
    Trae la rama, detiene el servicio, instala dependencias, aplica migraciones, vuelve a
    arrancar el servicio y espera a que /salud responda. Se detiene en el primer paso que falle.
    El servicio se vuelve a arrancar aunque falle un paso intermedio.
    Guía: docs/DESPLIEGUE.md

.EXAMPLE
    cd C:\ORBIT
    .\scripts\actualizar.ps1
#>
param(
    [string]$Servicio = "ORBIT",
    [string]$Salud = "http://127.0.0.1:8000/salud"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Write-Paso([string]$texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }

function Assert-Salida([string]$paso) {
    if ($LASTEXITCODE -ne 0) { throw "Falló: $paso (código $LASTEXITCODE)" }
}

$python = ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No existe $python. ¿Es la carpeta del hub y está creado el entorno virtual?" }
if (-not (Get-Service $Servicio -ErrorAction SilentlyContinue)) { throw "No existe el servicio '$Servicio' (ver docs/DESPLIEGUE.md, paso 2)." }

$rama = (git rev-parse --abbrev-ref HEAD); Assert-Salida "leer la rama"
$cambiosLocales = git status --porcelain --untracked-files=no; Assert-Salida "git status"
if ($cambiosLocales) {
    throw "Hay archivos versionados modificados en el servidor (no se editan a mano). Revisar con: git status"
}

Write-Paso "Traer '$rama' de GitHub"
$antes = (git rev-parse HEAD)
git pull --ff-only origin $rama; Assert-Salida "git pull"
$despues = (git rev-parse HEAD)
if ($antes -eq $despues) { Write-Host "Sin commits nuevos." } else { git --no-pager log --oneline "$antes..$despues" }

Write-Paso "Detener $Servicio"
Stop-Service $Servicio
try {
    Write-Paso "Dependencias"
    & $python -m pip install --disable-pip-version-check -q -r requirements.txt -r requirements-corte_caja.txt -r requirements-expedientes_seguros.txt
    Assert-Salida "pip install"

    Write-Paso "Migraciones"
    & $python -m flask --app wsgi db upgrade
    Assert-Salida "flask db upgrade"
}
finally {
    Write-Paso "Arrancar $Servicio"
    Start-Service $Servicio
}

Write-Paso "Comprobar $Salud"
$listo = $false
for ($i = 0; $i -lt 15 -and -not $listo; $i++) {
    try {
        $listo = (Invoke-WebRequest $Salud -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $listo) { throw "El hub no responde en $Salud. Revisar logs\servicio.log" }

Write-Host "`nListo: '$rama' en $($despues.Substring(0, 7))." -ForegroundColor Green
