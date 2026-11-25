<#
.SYNOPSIS
    Instala este proyecto en el servidor de pruebas 128.1.200.70, detrás del Caddy compartido.

.DESCRIPTION
    Se corre una vez, como administrador. Si se vuelve a correr, salta lo que ya esté hecho.
    Lo propio del proyecto (nombre, repositorio, puertos, .env...) está en despliegue.psd1; este
    archivo es igual en todos los proyectos (plantilla del skill caddy-deploy).

    No necesita el repositorio: se copian a una misma carpeta del servidor este archivo,
    despliegue.psd1 y el .env del equipo de desarrollo, y se ejecuta desde ahí.

      1. Revisa requisitos y que los puertos del proyecto estén libres.
      2. Crea la llave de solo lectura para GitHub (deploy key) y espera a que la pegues.
      3. Clona la rama, crea el .venv e instala dependencias.
      4. Copia el .env y le aplica los valores del servidor (Env en despliegue.psd1).
      5. Aplica migraciones, si el proyecto tiene.
      6. Instala el proyecto como servicio de Windows (NSSM), escuchando solo en 127.0.0.1.
      7. Instala el Caddy compartido si falta (C:\Caddy), agrega el sitio del proyecto y recarga
         Caddy sin cortar a los demás proyectos.
      8. Abre el puerto público en el firewall y comprueba la salud por HTTP y por HTTPS.

    Después, cada actualización es solo: cd <Carpeta>; .\scripts\actualizar.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\instalar_pruebas.ps1
#>
param(
    # Si el servidor sale a internet por proxy, p. ej. http://128.1.200.140:8080
    [string]$Proxy = ""
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ------------------------------------------------------------------ Servidor (igual para todos)
$Direccion = "128.1.200.70"
$Caddy = "C:\Caddy"   # caddy.exe, nssm.exe, Caddyfile, sitios\, datos\, logs\
$VersionCaddy = "2.10.0"
$UrlCaddy = "https://github.com/caddyserver/caddy/releases/download/v$VersionCaddy/caddy_${VersionCaddy}_windows_amd64.zip"
$UrlNssm = "https://nssm.cc/release/nssm-2.24.zip"

$P = Import-PowerShellDataFile (Join-Path $PSScriptRoot "despliegue.psd1")
$Nombre = $P.Nombre
$Carpeta = $P.Carpeta
$id = $Nombre.ToLower()

function Write-Paso([string]$texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }
function Write-Hecho([string]$texto) { Write-Host "   $texto" -ForegroundColor DarkGray }

function Assert-Salida([string]$paso) {
    if ($LASTEXITCODE -ne 0) { throw "Falló: $paso (código $LASTEXITCODE)" }
}

# Corre un programa externo sin mostrar su salida y devuelve si terminó bien. En PowerShell 5.1,
# redirigir el stderr de un programa con ErrorActionPreference=Stop aborta el script.
function Test-Comando([scriptblock]$comando) {
    $anterior = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try { & $comando *> $null; return $LASTEXITCODE -eq 0 } finally { $ErrorActionPreference = $anterior }
}

function Get-Descarga([string]$url, [string]$destino) {
    $opciones = @{ Uri = $url; OutFile = $destino; UseBasicParsing = $true }
    if ($Proxy) { $opciones.Proxy = $Proxy }
    Invoke-WebRequest @opciones
}

function Test-Puerto([int]$puerto) {
    [bool](Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue)
}

# Reemplaza la línea CLAVE=... (sin comentar) o la agrega al final.
function Set-ValorEnv([System.Collections.Generic.List[string]]$lineas, [string]$clave, [string]$valor) {
    $patron = "^\s*$([regex]::Escape($clave))\s*="
    for ($i = 0; $i -lt $lineas.Count; $i++) {
        if ($lineas[$i] -match $patron) { $lineas[$i] = "$clave=$valor"; return }
    }
    $lineas.Add("$clave=$valor")
}

function Get-ValorEnv([System.Collections.Generic.List[string]]$lineas, [string]$clave) {
    $patron = "^\s*$([regex]::Escape($clave))\s*=(.*)$"
    foreach ($linea in $lineas) { if ($linea -match $patron) { return $Matches[1].Trim().Trim('"', "'") } }
    return ""
}

function Install-Servicio([string]$nombre, [string]$programa, [string]$argumentos, [string]$directorio, [string]$log) {
    $nssm = Join-Path $Caddy "nssm.exe"
    if (Get-Service $nombre -ErrorAction SilentlyContinue) {
        Stop-Service $nombre
    } else {
        & $nssm install $nombre $programa $argumentos | Out-Null; Assert-Salida "nssm install $nombre"
    }
    & $nssm set $nombre Application $programa | Out-Null
    & $nssm set $nombre AppParameters $argumentos | Out-Null
    & $nssm set $nombre AppDirectory $directorio | Out-Null
    & $nssm set $nombre Start SERVICE_AUTO_START | Out-Null
    & $nssm set $nombre AppStdout $log | Out-Null
    & $nssm set $nombre AppStderr $log | Out-Null
    & $nssm set $nombre AppRotateFiles 1 | Out-Null
    & $nssm set $nombre AppRotateBytes 10485760 | Out-Null
    Start-Service $nombre
    Write-Hecho "Servicio $nombre en marcha."
}

function Wait-Salud([string]$url) {
    for ($i = 0; $i -lt 15; $i++) {
        try { if ((Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200) { return } } catch { Start-Sleep -Seconds 2 }
    }
    throw "No responde $url. Revisar $Carpeta\logs\servicio.log y $Caddy\logs\caddy.log"
}

# ------------------------------------------------------------------ 1. Requisitos
Write-Paso "Requisitos de $Nombre"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Abrir PowerShell como administrador." }
if ($Carpeta -match "\s") { throw "La carpeta no debe tener espacios: $Carpeta" }
foreach ($programa in "python", "git", "ssh-keygen") {
    if (-not (Get-Command $programa -ErrorAction SilentlyContinue)) {
        throw "Falta '$programa' en el PATH. Python 3 (para todos los usuarios, con 'Add to PATH') y Git for Windows."
    }
}
if ($P.RequiereOdbc -and -not (Get-OdbcDriver -Platform 64-bit | Where-Object { $_.Name -like "ODBC Driver 1* for SQL Server" })) {
    throw "Falta el ODBC Driver 17 o 18 for SQL Server (64 bits)."
}
if ($Proxy) { $env:HTTP_PROXY = $Proxy; $env:HTTPS_PROXY = $Proxy }  # para pip
Write-Hecho (python --version)

# Un puerto ocupado solo se acepta si es de este mismo proyecto (segunda corrida).
$yaInstalado = [bool](Get-Service $Nombre -ErrorAction SilentlyContinue)
if (-not $yaInstalado -and (Test-Puerto $P.PuertoInterno)) {
    throw "El puerto interno $($P.PuertoInterno) ya lo usa otro programa. Elegir otro en despliegue.psd1."
}
$sitio = Join-Path $Caddy "sitios\$id.caddy"
$otros = Get-ChildItem (Join-Path $Caddy "sitios") -Filter *.caddy -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -ne $sitio -and (Select-String -Path $_.FullName -Pattern ":$($P.PuertoPublico)\b|127\.0\.0\.1:$($P.PuertoInterno)\b" -Quiet) }
if ($otros) { throw "El puerto $($P.PuertoPublico) o $($P.PuertoInterno) ya lo tiene otro proyecto: $($otros.Name -join ', ')" }
Write-Hecho "Puertos: público $($P.PuertoPublico), interno $($P.PuertoInterno)."

$envOrigen = Join-Path $PSScriptRoot ".env"
$envDestino = Join-Path $Carpeta ".env"
if ($P.Env -and -not (Test-Path $envDestino) -and -not (Test-Path $envOrigen)) {
    throw "Copia el .env de tu equipo junto a este script ($envOrigen) y vuelve a correrlo."
}

# ------------------------------------------------------------------ 2. Llave de GitHub
Write-Paso "Acceso de solo lectura a GitHub"
# GitHub no acepta la misma deploy key en dos repositorios: una por proyecto.
$llave = Join-Path $HOME ".ssh\${id}_deploy"
if (-not (Test-Path $llave)) {
    New-Item -ItemType Directory -Force (Split-Path $llave) | Out-Null
    ssh-keygen -q -t ed25519 -f $llave -N '""' -C "$id-pruebas"; Assert-Salida "ssh-keygen"
}
# git ejecuta sshCommand con sh: rutas con / y entre comillas simples.
$sshCommand = "ssh -i '$($llave -replace '\\', '/')' -o StrictHostKeyChecking=accept-new"
$verGitHub = { git -c core.sshCommand=$sshCommand ls-remote $P.Repositorio $P.Rama }
while (-not (Test-Comando $verGitHub)) {
    Write-Host "`nPega esta llave en GitHub: repositorio -> Settings -> Deploy keys -> Add deploy key" -ForegroundColor Yellow
    Write-Host "(título '$id-pruebas', SIN marcar 'Allow write access'):`n"
    Get-Content "$llave.pub" | Write-Host -ForegroundColor White
    Read-Host "`nEnter cuando esté guardada (Ctrl+C para salir)"
}
Write-Hecho "GitHub responde."

# ------------------------------------------------------------------ 3. Código y dependencias
Write-Paso "Código ($($P.Rama)) y dependencias"
if (-not (Test-Path (Join-Path $Carpeta ".git"))) {
    git -c core.sshCommand=$sshCommand clone -b $P.Rama $P.Repositorio $Carpeta; Assert-Salida "git clone"
} else {
    Write-Hecho "Ya estaba clonado; para traer lo nuevo se usa actualizar.ps1."
}
Set-Location $Carpeta
git config core.sshCommand $sshCommand; Assert-Salida "git config"  # actualizar.ps1 usa la misma llave

# Windows no deja reemplazar paquetes de Python en uso.
if ($yaInstalado) { Stop-Service $Nombre }
$python = Join-Path $Carpeta ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { python -m venv .venv; Assert-Salida "python -m venv" }
if ($P.Requisitos) {
    $argsPip = @("-m", "pip", "install", "--disable-pip-version-check", "-q")
    foreach ($archivo in $P.Requisitos) { $argsPip += @("-r", $archivo) }
    & $python @argsPip; Assert-Salida "pip install"
}
New-Item -ItemType Directory -Force (Join-Path $Carpeta "logs") | Out-Null

# ------------------------------------------------------------------ 4. .env del servidor
if ($P.Env) {
    Write-Paso ".env"
    if (-not (Test-Path $envDestino)) { Copy-Item $envOrigen $envDestino }
    $lineas = [System.Collections.Generic.List[string]]::new()
    foreach ($l in (Get-Content $envDestino -Encoding UTF8)) { $lineas.Add($l) }

    foreach ($clave in $P.EnvObligatorias) {
        $valor = Get-ValorEnv $lineas $clave
        if (-not $valor) { throw "$clave está vacío en $envDestino." }
        if ($valor -match "localdb") { throw "$clave apunta a LocalDB del equipo de desarrollo; en el servidor no existe." }
    }
    if ($P.EnvSecreto -and -not (Get-ValorEnv $lineas $P.EnvSecreto)) {
        Set-ValorEnv $lineas $P.EnvSecreto (& $python -c "import secrets; print(secrets.token_hex(32))")
    }
    foreach ($clave in $P.Env.Keys) { Set-ValorEnv $lineas $clave ([string]$P.Env[$clave]) }
    [IO.File]::WriteAllLines($envDestino, $lineas, (New-Object Text.UTF8Encoding($false)))
    icacls $envDestino /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:R" | Out-Null  # Administradores y SYSTEM
    Assert-Salida "icacls .env"
    Write-Hecho ("Ajustado: " + (($P.Env.Keys | Sort-Object) -join ", "))
}

# ------------------------------------------------------------------ 5. Migraciones
if ($P.Migraciones) {
    Write-Paso "Migraciones pendientes"
    & $python @($P.Migraciones); Assert-Salida "migraciones"
}

# ------------------------------------------------------------------ 6. Caddy compartido (si falta)
Write-Paso "Caddy compartido ($Caddy)"
New-Item -ItemType Directory -Force (Join-Path $Caddy "sitios"), (Join-Path $Caddy "logs"), (Join-Path $Caddy "datos") | Out-Null
$nssm = Join-Path $Caddy "nssm.exe"
$caddyExe = Join-Path $Caddy "caddy.exe"
$temporal = Join-Path $env:TEMP "caddy-deploy"
New-Item -ItemType Directory -Force $temporal | Out-Null
if (-not (Test-Path $nssm)) {
    try { Get-Descarga $UrlNssm "$temporal\nssm.zip" } catch {
        throw "No se pudo descargar NSSM ($UrlNssm). Descárgalo a mano y deja win64\nssm.exe en $nssm."
    }
    Expand-Archive "$temporal\nssm.zip" "$temporal\nssm" -Force
    Copy-Item (Get-ChildItem "$temporal\nssm" -Recurse -Filter nssm.exe | Where-Object { $_.FullName -match "win64" } | Select-Object -First 1).FullName $nssm
}
if (-not (Test-Path $caddyExe)) {
    Get-Descarga $UrlCaddy "$temporal\caddy.zip"
    Expand-Archive "$temporal\caddy.zip" "$temporal\caddy" -Force
    Copy-Item "$temporal\caddy\caddy.exe" $caddyExe
}
$caddyfile = Join-Path $Caddy "Caddyfile"
$raiz = $Caddy -replace '\\', '/'
if (-not (Test-Path $caddyfile)) {
    # Sin redirección en el 80 (puede estar ocupado) y sin tocar la confianza de Windows: el
    # servicio no tiene escritorio para confirmar. Los certificados quedan en datos\.
    @"
{
	auto_https disable_redirects
	skip_install_trust
	storage file_system $raiz/datos
}

import $raiz/sitios/*.caddy
"@ | Set-Content $caddyfile -Encoding ASCII
}
Write-Hecho (& $caddyExe version)

# ------------------------------------------------------------------ 7. Servicio del proyecto y sitio
Write-Paso "Servicio $Nombre"
Install-Servicio $Nombre $python $P.Arranque $Carpeta (Join-Path $Carpeta "logs\servicio.log")
Wait-Salud "http://127.0.0.1:$($P.PuertoInterno)$($P.Salud)"

Write-Paso "Sitio https://${Direccion}:$($P.PuertoPublico)"
@"
https://${Direccion}:$($P.PuertoPublico) {
	tls internal
	reverse_proxy 127.0.0.1:$($P.PuertoInterno)
}
"@ | Set-Content $sitio -Encoding ASCII
if (-not (Test-Comando { & $caddyExe validate --config $caddyfile --adapter caddyfile })) {
    Remove-Item $sitio
    throw "La configuración de Caddy no es válida con este sitio. Probar: $caddyExe validate --config $caddyfile"
}
if (Get-Service "Caddy" -ErrorAction SilentlyContinue) {
    # reload aplica el sitio nuevo sin cortar a los otros proyectos
    if (-not (Test-Comando { & $caddyExe reload --config $caddyfile --adapter caddyfile })) { Restart-Service "Caddy" }
    Write-Hecho "Caddy recargado."
} else {
    Install-Servicio "Caddy" $caddyExe "run --config $caddyfile --adapter caddyfile" $Caddy (Join-Path $Caddy "logs\caddy.log")
}

# ------------------------------------------------------------------ 8. Firewall y verificación
Write-Paso "Firewall"
$regla = "$Nombre pruebas"
if (-not (Get-NetFirewallRule -DisplayName $regla -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $regla -Direction Inbound -Protocol TCP -LocalPort $P.PuertoPublico -Action Allow | Out-Null
}
Write-Hecho "Abierto el $($P.PuertoPublico); el $($P.PuertoInterno) sigue cerrado."

Write-Paso "Comprobar"
# El certificado es interno de Caddy: aquí no se valida, solo que responda.
[Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
$url = "https://${Direccion}:$($P.PuertoPublico)"
Wait-Salud "$url$($P.Salud)"
Write-Hecho "$url$($P.Salud) OK"

Write-Host "`nListo: $url" -ForegroundColor Green
Write-Host "El navegador avisará del certificado. Para quitar el aviso en un equipo, instalar"
Write-Host "$Caddy\datos\pki\authorities\local\root.crt en 'Entidades de certificación raíz de confianza'."
Write-Host "Para actualizar después de un push:  cd $Carpeta; .\scripts\actualizar.ps1"
