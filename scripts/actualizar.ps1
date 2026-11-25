<#
.SYNOPSIS
    Actualiza el proyecto en un servidor a lo último de su rama en GitHub.

.DESCRIPTION
    Trae la rama en la que está la carpeta, detiene el servicio, instala dependencias, aplica
    migraciones, vuelve a arrancar el servicio y espera a que responda la salud. Se detiene en el
    primer paso que falle; el servicio se vuelve a arrancar aunque falle un paso intermedio.
    Lo propio del proyecto (servicio, requirements, migraciones, puerto) está en despliegue.psd1;
    este archivo es igual en todos los proyectos (plantilla del skill caddy-deploy).

.EXAMPLE
    cd C:\<CARPETA>
    .\scripts\actualizar.ps1
#>
param(
    [string]$Servicio = "",
    [string]$Salud = ""
)

$ErrorActionPreference = "Stop"
$P = Import-PowerShellDataFile (Join-Path $PSScriptRoot "despliegue.psd1")
if (-not $Servicio) { $Servicio = $P.Nombre }
if (-not $Salud) {
    # En el servidor de pruebas el puerto real es el que eligió instalar_pruebas.ps1 (puede no ser
    # el preferido): está en el sitio de Caddy. Sin sitio (p. ej. producción con IIS), el del psd1.
    $puerto = $P.PuertoInterno
    $sitio = "C:\Caddy\sitios\$($P.Nombre.ToLower()).caddy"
    if ((Test-Path $sitio) -and ((Get-Content $sitio -Raw) -match 'reverse_proxy 127\.0\.0\.1:(\d+)')) { $puerto = $Matches[1] }
    $Salud = "http://127.0.0.1:$puerto$($P.Salud)"
}
Set-Location (Split-Path -Parent $PSScriptRoot)

function Write-Paso([string]$texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }

function Assert-Salida([string]$paso) {
    if ($LASTEXITCODE -ne 0) { throw "Falló: $paso (código $LASTEXITCODE)" }
}

$python = ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No existe $python. ¿Es la carpeta del proyecto y está creado el entorno virtual?" }
if (-not (Get-Service $Servicio -ErrorAction SilentlyContinue)) { throw "No existe el servicio '$Servicio' (correr antes instalar_pruebas.ps1)." }

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
# El pull pudo traer cambios en despliegue.psd1.
$P = Import-PowerShellDataFile (Join-Path $PSScriptRoot "despliegue.psd1")

Write-Paso "Detener $Servicio"
Stop-Service $Servicio
try {
    if ($P.Requisitos) {
        Write-Paso "Dependencias"
        $argsPip = @("-m", "pip", "install", "--disable-pip-version-check", "-q")
        foreach ($archivo in $P.Requisitos) { $argsPip += @("-r", $archivo) }
        & $python @argsPip; Assert-Salida "pip install"
    }
    if ($P.Migraciones) {
        Write-Paso "Migraciones"
        & $python @($P.Migraciones); Assert-Salida "migraciones"
    }
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
if (-not $listo) { throw "No responde $Salud. Revisar logs\servicio.log" }

Write-Host "`nListo: '$rama' en $($despues.Substring(0, 7))." -ForegroundColor Green
