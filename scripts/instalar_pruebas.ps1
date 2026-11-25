<#
.SYNOPSIS
    Instala este proyecto en el servidor de pruebas 128.1.200.70, detrás del Caddy compartido.

.DESCRIPTION
    Se corre una vez, como administrador. Si se vuelve a correr, salta lo que ya esté hecho.
    Lo propio del proyecto (nombre, repositorio, puertos, .env...) está en despliegue.psd1; este
    archivo es igual en todos los proyectos (plantilla del skill caddy-deploy).

    No necesita el repositorio: se copian a una misma carpeta del servidor este archivo,
    despliegue.psd1 y el .env del equipo de desarrollo, y se ejecuta desde ahí.

      1. Revisa requisitos y elige puertos: los de despliegue.psd1 o, si están ocupados, el
         siguiente libre (en una segunda corrida, los mismos que ya tenía).
      2. Crea la llave de solo lectura para GitHub (deploy key) y espera a que la pegues.
      3. Clona la rama, crea el .venv con el Python más nuevo que cumpla PythonMinimo (no el del
         PATH) e instala dependencias. Un .venv con un Python viejo se rehace.
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

function Test-Salud([string]$url) {
    for ($i = 0; $i -lt 15; $i++) {
        try { if ((Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200) { return $true } } catch { Start-Sleep -Seconds 2 }
    }
    return $false
}

# Versión "3.13" de un python.exe, o $null si no corre.
function Get-VersionPython([string]$exe) {
    try {
        $anterior = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        $v = & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -match '^\d+\.\d+$') { return [version]$v }
    } catch { } finally { $ErrorActionPreference = $anterior }
    return $null
}

# El python del PATH puede ser viejo (en el .70 es 3.10): se busca el más nuevo que cumpla el mínimo
# entre el lanzador py, el PATH y las carpetas de instalación habituales.
function Find-Python([version]$minimo) {
    $candidatos = [System.Collections.Generic.List[string]]::new()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $anterior = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        foreach ($linea in (py -0p 2>$null)) { if ($linea -match '([A-Za-z]:\\.*python\.exe)\s*$') { $candidatos.Add($Matches[1]) } }
        $ErrorActionPreference = $anterior
    }
    Get-Command python -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' } | ForEach-Object { $candidatos.Add($_.Source) }
    foreach ($patron in "$env:ProgramFiles\Python3*\python.exe", "C:\Python3*\python.exe",
                        "$env:LOCALAPPDATA\Programs\Python\*\python.exe", "$env:LOCALAPPDATA\Programs\Python\*\tools\python.exe") {
        Get-ChildItem $patron -ErrorAction SilentlyContinue | ForEach-Object { $candidatos.Add($_.FullName) }
    }
    $mejor = $null; $mejorVersion = $null
    foreach ($exe in ($candidatos | Select-Object -Unique)) {
        $v = Get-VersionPython $exe
        if ($v -and $v -ge $minimo -and (-not $mejorVersion -or $v -gt $mejorVersion)) { $mejor = $exe; $mejorVersion = $v }
    }
    if (-not $mejor) { throw "No hay Python $minimo o más nuevo. Instalar Python 3.13 de python.org (para todos los usuarios)." }
    return $mejor
}

# ------------------------------------------------------------------ 1. Requisitos
Write-Paso "Requisitos de $Nombre"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Abrir PowerShell como administrador." }
if ($Carpeta -match "\s") { throw "La carpeta no debe tener espacios: $Carpeta" }
foreach ($programa in "git", "ssh-keygen") {
    if (-not (Get-Command $programa -ErrorAction SilentlyContinue)) { throw "Falta '$programa' en el PATH: instalar Git for Windows." }
}
if ($P.RequiereOdbc -and -not (Get-OdbcDriver -Platform 64-bit | Where-Object { $_.Name -like "ODBC Driver 1* for SQL Server" })) {
    throw "Falta el ODBC Driver 17 o 18 for SQL Server (64 bits)."
}
if ($Proxy) { $env:HTTP_PROXY = $Proxy; $env:HTTPS_PROXY = $Proxy }  # para pip
$pythonMinimo = [version]$(if ($P.PythonMinimo) { $P.PythonMinimo } else { "3.11" })
$pythonBase = Find-Python $pythonMinimo
Write-Hecho "Python $(Get-VersionPython $pythonBase): $pythonBase"

# Puertos: los de despliegue.psd1 son preferidos. Si están ocupados se toma el siguiente libre;
# en una segunda corrida se repiten los que ya tenía. Quedan anotados en el sitio de Caddy, que
# es de donde los lee actualizar.ps1.
if (Get-Service $Nombre -ErrorAction SilentlyContinue) { Stop-Service $Nombre }  # libera su puerto
$sitio = Join-Path $Caddy "sitios\$id.caddy"
$internoPreferido = [int]$P.PuertoInterno
$publicoPreferido = [int]$P.PuertoPublico
if (Test-Path $sitio) {
    $texto = Get-Content $sitio -Raw
    if ($texto -match ':(\d+)\s*\{') { $publicoPreferido = [int]$Matches[1] }
    if ($texto -match 'reverse_proxy 127\.0\.0\.1:(\d+)') { $internoPreferido = [int]$Matches[1] }
}
# Puertos de otros proyectos en Caddy (aunque su servicio esté detenido), 80/443 y la administración de Caddy.
$reservados = [System.Collections.Generic.List[int]]@(80, 443, 2019)
Get-ChildItem (Join-Path $Caddy "sitios") -Filter *.caddy -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "$id.caddy" } |
    ForEach-Object { foreach ($m in [regex]::Matches((Get-Content $_.FullName -Raw), ':(\d{2,5})\b')) { $reservados.Add([int]$m.Groups[1].Value) } }

function Find-PuertoLibre([int]$desde, [string]$procesoPermitido) {
    for ($puerto = $desde; $puerto -lt $desde + 100; $puerto++) {
        if ($reservados.Contains($puerto)) { continue }
        $conexion = Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $conexion) { return $puerto }
        $proceso = (Get-Process -Id $conexion.OwningProcess -ErrorAction SilentlyContinue).ProcessName
        if ($procesoPermitido -and $proceso -eq $procesoPermitido) { return $puerto }
    }
    throw "No hay puerto libre entre $desde y $($desde + 99)."
}
$interno = Find-PuertoLibre $internoPreferido ""
$reservados.Add($interno)
$publico = Find-PuertoLibre $publicoPreferido "caddy"  # Caddy ya escucha en el de este sitio
Write-Hecho "Puertos: público $publico, interno $interno."
if ($interno -ne $P.PuertoInterno -or $publico -ne $P.PuertoPublico) {
    Write-Hecho "(preferidos $($P.PuertoPublico)/$($P.PuertoInterno) ocupados o ya asignados antes)"
}

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

$python = Join-Path $Carpeta ".venv\Scripts\python.exe"
if ((Test-Path $python) -and -not ((Get-VersionPython $python) -ge $pythonMinimo)) {
    Write-Hecho "El .venv tiene un Python viejo o roto: se rehace."
    Remove-Item (Join-Path $Carpeta ".venv") -Recurse -Force
}
if (-not (Test-Path $python)) { & $pythonBase -m venv .venv; Assert-Salida "python -m venv" }
Write-Hecho "Entorno: Python $(Get-VersionPython $python)"
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
    if ($P.EnvPuerto) { Set-ValorEnv $lineas $P.EnvPuerto "$interno" }
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
# {puerto} en Arranque, para proyectos que reciben el puerto como argumento y no por el .env
Install-Servicio $Nombre $python ($P.Arranque -replace '\{puerto\}', "$interno") $Carpeta (Join-Path $Carpeta "logs\servicio.log")
if (-not (Test-Salud "http://127.0.0.1:$interno$($P.Salud)")) {
    throw "$Nombre no responde en http://127.0.0.1:$interno$($P.Salud). Revisar $Carpeta\logs\servicio.log"
}
Write-Hecho "Responde en 127.0.0.1:$interno."

Write-Paso "Sitio https://${Direccion}:$publico"
@"
https://${Direccion}:$publico {
	tls internal
	reverse_proxy 127.0.0.1:$interno
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
Remove-NetFirewallRule -DisplayName $regla -ErrorAction SilentlyContinue  # por si cambió el puerto
New-NetFirewallRule -DisplayName $regla -Direction Inbound -Protocol TCP -LocalPort $publico -Action Allow | Out-Null
Write-Hecho "Abierto el $publico; el $interno sigue cerrado."

Write-Paso "Comprobar HTTPS"
# El certificado es interno de Caddy: no se valida (-k). curl.exe viene con Windows 10/Server 2019;
# PowerShell 5.1 falla con certificados no confiables aunque se le diga que los acepte.
$url = "https://${Direccion}:$publico"
$https = $false
if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    for ($i = 0; $i -lt 10 -and -not $https; $i++) {
        $codigo = & curl.exe -sk -o NUL -w "%{http_code}" --max-time 5 "$url$($P.Salud)" 2>$null
        if ($codigo -eq "200") { $https = $true } else { Start-Sleep -Seconds 2 }
    }
}
if ($https) {
    Write-Hecho "$url$($P.Salud) OK"
} else {
    # No es fatal: el proyecto ya respondió por dentro y Caddy está en marcha. Desde el mismo
    # servidor a veces no se llega a su propia IP; lo que vale es entrar desde otro equipo.
    Write-Warning "No se pudo comprobar $url desde este servidor. Abrirlo desde otro equipo; si no entra, revisar $Caddy\logs\caddy.log"
}

Write-Host "`nListo: $url" -ForegroundColor Green
Write-Host "El navegador avisará del certificado. Para quitar el aviso en un equipo, instalar"
Write-Host "$Caddy\datos\pki\authorities\local\root.crt en 'Entidades de certificación raíz de confianza'."
Write-Host "Para actualizar después de un push:  cd $Carpeta; .\scripts\actualizar.ps1"
