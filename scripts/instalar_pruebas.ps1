<#
.SYNOPSIS
    Instala el hub de pruebas en un servidor: rama dev, Waitress como servicio y Caddy con HTTPS.

.DESCRIPTION
    Se corre una vez, como administrador. Si se vuelve a correr, salta lo que ya esté hecho.
    No necesita el repositorio: se copia este archivo y el .env de tu equipo a una misma carpeta
    del servidor y se ejecuta desde ahí. El script:

      1. Revisa Python, Git y el driver ODBC.
      2. Crea la llave de solo lectura para GitHub (deploy key) y espera a que la pegues.
      3. Clona la rama dev en -Carpeta, crea el .venv e instala dependencias.
      4. Copia el .env y le ajusta lo propio del servidor (production, proxy, HTTPS, simulación).
      5. Aplica migraciones pendientes (normalmente ninguna: la base es la misma de tu equipo).
      6. Descarga NSSM y Caddy, escribe el Caddyfile e instala los servicios ORBIT y ORBIT-Caddy.
      7. Abre el puerto en el firewall y comprueba /salud por HTTP y por HTTPS.

    Después, cada actualización es solo: cd C:\ORBIT; .\scripts\actualizar.ps1
    Guía: docs/DESPLIEGUE.md

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\instalar_pruebas.ps1
#>
param(
    [string]$Carpeta = "C:\ORBIT",
    [string]$Repositorio = "git@github.com:FernandHanser/Orbit_Canella.git",
    [string]$Rama = "dev",
    [string]$Direccion = "128.1.200.70",
    [int]$Puerto = 8443,
    # Si el servidor sale a internet por proxy, p. ej. http://128.1.200.140:8080
    [string]$Proxy = ""
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$VersionCaddy = "2.10.0"
$UrlCaddy = "https://github.com/caddyserver/caddy/releases/download/v$VersionCaddy/caddy_${VersionCaddy}_windows_amd64.zip"
$UrlNssm = "https://nssm.cc/release/nssm-2.24.zip"
$Requisitos = @("requirements.txt", "requirements-corte_caja.txt", "requirements-expedientes_seguros.txt")

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

# ------------------------------------------------------------------ 1. Requisitos
Write-Paso "Requisitos"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Abrir PowerShell como administrador." }
if ($Carpeta -match "\s") { throw "La carpeta no debe tener espacios: $Carpeta" }
foreach ($programa in "python", "git", "ssh-keygen") {
    if (-not (Get-Command $programa -ErrorAction SilentlyContinue)) {
        throw "Falta '$programa' en el PATH. Python 3.13 (para todos los usuarios, con 'Add to PATH') y Git for Windows."
    }
}
if (-not (Get-OdbcDriver -Platform 64-bit | Where-Object { $_.Name -like "ODBC Driver 1* for SQL Server" })) {
    throw "Falta el ODBC Driver 17 o 18 for SQL Server (64 bits)."
}
if ($Proxy) { $env:HTTP_PROXY = $Proxy; $env:HTTPS_PROXY = $Proxy }  # para pip
Write-Hecho (python --version)

# Buscar el .env junto a este script si aún no está en la carpeta del hub.
$envOrigen = Join-Path $PSScriptRoot ".env"
$envDestino = Join-Path $Carpeta ".env"
if (-not (Test-Path $envDestino) -and -not (Test-Path $envOrigen)) {
    throw "Copia el .env de tu equipo junto a este script ($envOrigen) y vuelve a correrlo."
}

# ------------------------------------------------------------------ 2. Llave de GitHub
Write-Paso "Acceso de solo lectura a GitHub"
$llave = Join-Path $HOME ".ssh\orbit_deploy"
if (-not (Test-Path $llave)) {
    New-Item -ItemType Directory -Force (Split-Path $llave) | Out-Null
    ssh-keygen -q -t ed25519 -f $llave -N '""' -C "orbit-pruebas"; Assert-Salida "ssh-keygen"
}
# git ejecuta sshCommand con sh: rutas con / y entre comillas simples.
$sshCommand = "ssh -i '$($llave -replace '\\', '/')' -o StrictHostKeyChecking=accept-new"
$verGitHub = { git -c core.sshCommand=$sshCommand ls-remote $Repositorio $Rama }
while (-not (Test-Comando $verGitHub)) {
    Write-Host "`nPega esta llave en GitHub: Orbit_Canella -> Settings -> Deploy keys -> Add deploy key" -ForegroundColor Yellow
    Write-Host "(título 'orbit-pruebas', SIN marcar 'Allow write access'):`n"
    Get-Content "$llave.pub" | Write-Host -ForegroundColor White
    Read-Host "`nEnter cuando esté guardada (Ctrl+C para salir)"
}
Write-Hecho "GitHub responde."

# ------------------------------------------------------------------ 3. Código y dependencias
Write-Paso "Código ($Rama) y dependencias"
if (-not (Test-Path (Join-Path $Carpeta ".git"))) {
    git -c core.sshCommand=$sshCommand clone -b $Rama $Repositorio $Carpeta; Assert-Salida "git clone"
} else {
    Write-Hecho "Ya estaba clonado; para traer lo nuevo se usa actualizar.ps1."
}
Set-Location $Carpeta
git config core.sshCommand $sshCommand; Assert-Salida "git config"  # actualizar.ps1 usa la misma llave

# En una segunda corrida: Windows no deja reemplazar paquetes de Python en uso.
if (Get-Service "ORBIT" -ErrorAction SilentlyContinue) { Stop-Service "ORBIT" }
$python = Join-Path $Carpeta ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { python -m venv .venv; Assert-Salida "python -m venv" }
$argsPip = @("-m", "pip", "install", "--disable-pip-version-check", "-q")
foreach ($archivo in $Requisitos) { $argsPip += @("-r", $archivo) }
& $python @argsPip; Assert-Salida "pip install"
New-Item -ItemType Directory -Force (Join-Path $Carpeta "logs"), (Join-Path $Carpeta "herramientas") | Out-Null

# ------------------------------------------------------------------ 4. .env del servidor
Write-Paso ".env"
if (-not (Test-Path $envDestino)) { Copy-Item $envOrigen $envDestino }
$lineas = [System.Collections.Generic.List[string]]::new()
foreach ($l in (Get-Content $envDestino -Encoding UTF8)) { $lineas.Add($l) }

$base = Get-ValorEnv $lineas "DATABASE_URL"
if (-not $base) { throw "DATABASE_URL está vacío en $envDestino." }
if ($base -match "localdb") { throw "DATABASE_URL apunta a LocalDB de tu equipo; en el servidor debe ser la base en SQL Server." }
if (-not (Get-ValorEnv $lineas "SECRET_KEY")) {
    Set-ValorEnv $lineas "SECRET_KEY" (& $python -c "import secrets; print(secrets.token_hex(32))")
}
Set-ValorEnv $lineas "AUTOMATE_ENV" "production"
Set-ValorEnv $lineas "HOST" "127.0.0.1"           # Waitress solo para Caddy; el 8000 no sale del servidor
Set-ValorEnv $lineas "PORT" "8000"
Set-ValorEnv $lineas "PROXY_CONFIABLE" "127.0.0.1" # IP real del usuario detrás de Caddy
Set-ValorEnv $lineas "SESSION_COOKIE_SECURE" "1"
Set-ValorEnv $lineas "LOG_DIR" ""                  # la ruta de tu equipo no existe aquí: logs\ del hub
Set-ValorEnv $lineas "CORTE_CAJA_MODO" "simulacion"
[IO.File]::WriteAllLines($envDestino, $lineas, (New-Object Text.UTF8Encoding($false)))
icacls $envDestino /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:R" | Out-Null  # Administradores y SYSTEM
Assert-Salida "icacls .env"
Write-Hecho "production, proxy 127.0.0.1, cookie segura, corte de caja en simulación."

# ------------------------------------------------------------------ 5. Migraciones
Write-Paso "Migraciones pendientes"
& $python -m flask --app wsgi db upgrade; Assert-Salida "flask db upgrade"

# ------------------------------------------------------------------ 6. NSSM, Caddy y servicios
Write-Paso "NSSM y Caddy"
$herramientas = Join-Path $Carpeta "herramientas"
$nssm = Join-Path $herramientas "nssm.exe"
$caddy = Join-Path $herramientas "caddy.exe"
$temporal = Join-Path $env:TEMP "orbit-instalacion"
New-Item -ItemType Directory -Force $temporal | Out-Null

if (-not (Test-Path $nssm)) {
    try {
        Get-Descarga $UrlNssm "$temporal\nssm.zip"
    } catch {
        throw "No se pudo descargar NSSM ($UrlNssm). Descárgalo a mano y deja win64\nssm.exe en $nssm."
    }
    Expand-Archive "$temporal\nssm.zip" "$temporal\nssm" -Force
    Copy-Item (Get-ChildItem "$temporal\nssm" -Recurse -Filter nssm.exe | Where-Object { $_.FullName -match "win64" } | Select-Object -First 1).FullName $nssm
}
if (-not (Test-Path $caddy)) {
    Get-Descarga $UrlCaddy "$temporal\caddy.zip"
    Expand-Archive "$temporal\caddy.zip" "$temporal\caddy" -Force
    Copy-Item "$temporal\caddy\caddy.exe" $caddy
}
Write-Hecho (& $caddy version)

$caddyfile = Join-Path $herramientas "Caddyfile"
@"
https://${Direccion}:$Puerto {
	tls internal
	reverse_proxy 127.0.0.1:8000
}
"@ | Set-Content $caddyfile -Encoding ASCII
if (-not (Test-Comando { & $caddy validate --config $caddyfile --adapter caddyfile })) {
    throw "Caddyfile inválido: $caddyfile"
}

Write-Paso "Servicios"
function Install-Servicio([string]$nombre, [string]$programa, [string]$argumentos, [string]$log) {
    if (Get-Service $nombre -ErrorAction SilentlyContinue) {
        Stop-Service $nombre
    } else {
        & $nssm install $nombre $programa $argumentos | Out-Null; Assert-Salida "nssm install $nombre"
    }
    & $nssm set $nombre Application $programa | Out-Null
    & $nssm set $nombre AppParameters $argumentos | Out-Null
    & $nssm set $nombre AppDirectory $Carpeta | Out-Null
    & $nssm set $nombre Start SERVICE_AUTO_START | Out-Null
    & $nssm set $nombre AppStdout $log | Out-Null
    & $nssm set $nombre AppStderr $log | Out-Null
    & $nssm set $nombre AppRotateFiles 1 | Out-Null
    & $nssm set $nombre AppRotateBytes 10485760 | Out-Null
    Start-Service $nombre
    Write-Hecho "$nombre en marcha."
}
Install-Servicio "ORBIT" $python "serve.py" (Join-Path $Carpeta "logs\servicio.log")
Install-Servicio "ORBIT-Caddy" $caddy "run --config $caddyfile --adapter caddyfile" (Join-Path $Carpeta "logs\caddy.log")

# ------------------------------------------------------------------ 7. Firewall y verificación
Write-Paso "Firewall"
if (-not (Get-NetFirewallRule -DisplayName "ORBIT pruebas" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "ORBIT pruebas" -Direction Inbound -Protocol TCP -LocalPort $Puerto -Action Allow | Out-Null
}
Write-Hecho "Abierto el $Puerto (el 8000 sigue cerrado)."

Write-Paso "Comprobar"
# El certificado es interno de Caddy: aquí no se valida, solo que responda.
[Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
foreach ($url in "http://127.0.0.1:8000/salud", "https://${Direccion}:$Puerto/salud") {
    $listo = $false
    for ($i = 0; $i -lt 15 -and -not $listo; $i++) {
        try { $listo = (Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $listo) { throw "No responde $url. Revisar logs\servicio.log y logs\caddy.log" }
    Write-Hecho "$url OK"
}

Write-Host "`nListo: entra a https://${Direccion}:$Puerto con tu usuario de STOD." -ForegroundColor Green
Write-Host "El navegador avisará del certificado: en pruebas se acepta."
Write-Host "Para actualizar después de un push a dev:  cd $Carpeta; .\scripts\actualizar.ps1"
