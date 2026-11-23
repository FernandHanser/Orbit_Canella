# Publicar el hub en la red (Windows Server + IIS + HTTPS)

Cómo dejar ORBIT Canella accesible para los usuarios de la red, con HTTPS, como servicio de
Windows que arranca solo.

```
Navegador ──HTTPS 443──▶ IIS (certificado, URL Rewrite + ARR) ──HTTP 127.0.0.1:8000──▶ Waitress (serve.py) ──▶ Flask
```

- **IIS** pone el certificado y reenvía todo a Waitress. Es lo único que se abre a la red.
- **Waitress** escucha solo en `127.0.0.1`: el puerto 8000 nunca sale del servidor, así las
  contraseñas de STOD no viajan sin cifrar (hallazgo N1 de [ARQUITECTURA.md](ARQUITECTURA.md)).
- **`PROXY_CONFIABLE=127.0.0.1`** hace que Waitress tome la IP real del usuario de la cabecera
  `X-Forwarded-For` que pone IIS. Sin esto todos llegan con la IP del proxy y el bloqueo de login
  por IP bloquearía a todos a la vez (hallazgo N3). Las cabeceras `X-Forwarded-*` que no vengan
  del proxy se descartan, así nadie puede falsear su IP. Prueba: `tests/test_servidor.py`.

Los comandos son de **PowerShell como administrador** en el servidor. Las rutas de ejemplo
usan `C:\ORBIT`; cámbialas si el hub vive en otra carpeta.

---

## Lo que hay que definir antes (con TI)

| Qué | Para qué | Ejemplo |
|---|---|---|
| Servidor | Windows Server con IIS, con acceso a SQL Server (AUTOMATE_CANELLA, STOD, SAP) y a las carpetas de red de los módulos | — |
| Nombre DNS | La dirección que usarán los usuarios | `orbit.canella.com.gt` |
| Certificado | Emitido para ese nombre (CA interna de Canella o pública), instalado en *Equipo local → Personal* | — |
| Cuenta de servicio | Cuenta de dominio con la que corre el hub; necesita leer y escribir en las carpetas de red de los módulos | `CANELLA\svc_orbit` |

---

## 1. Instalar el hub

1. Instalar **Python 3.13** (marcar «Add to PATH» e instalar para todos los usuarios) y el
   **ODBC Driver 17 o 18 for SQL Server**.
2. Clonar la rama `main` e instalar dependencias:

   ```powershell
   git clone -b main <url-del-repo> C:\ORBIT
   cd C:\ORBIT
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt -r requirements-corte_caja.txt -r requirements-expedientes_seguros.txt
   ```

3. Crear `C:\ORBIT\.env` a partir de `.env.example`. Lo propio de producción:

   ```ini
   AUTOMATE_ENV=production
   SECRET_KEY=<generar: .venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))">
   DATABASE_URL=<cadena de AUTOMATE_CANELLA>
   STOD_SERVER=...
   STOD_USERNAME=...
   STOD_PASSWORD=...
   # Servidor
   HOST=127.0.0.1
   PORT=8000
   HILOS=8
   PROXY_CONFIABLE=127.0.0.1
   ```

   `SESSION_COOKIE_SECURE` no se toca: en producción vale 1 y la cookie solo viaja por HTTPS.
   Más las variables `EXPEDIENTES_*` y `CORTE_CAJA_*` de los módulos (ver sus guías).

4. Dejar `.env` legible solo para administradores y la cuenta de servicio:

   ```powershell
   icacls C:\ORBIT\.env /inheritance:r /grant:r "Administradores:F" "CANELLA\svc_orbit:R"
   ```

5. Aplicar migraciones (solo cuando el responsable de la base lo autorice):

   ```powershell
   $env:AUTOMATE_ENV="production"; .venv\Scripts\flask --app wsgi db upgrade
   ```

6. Probar a mano antes de seguir:

   ```powershell
   .venv\Scripts\python serve.py
   # en otra ventana:
   Invoke-WebRequest http://127.0.0.1:8000/salud    # → {"estado":"ok"}
   ```

   Ctrl+C para detenerlo.

## 2. Waitress como servicio de Windows (NSSM)

[NSSM](https://nssm.cc) convierte `serve.py` en un servicio que arranca con el equipo y se
reinicia si se cae. Copiar `nssm.exe` a `C:\ORBIT\herramientas\` (o a cualquier carpeta en el PATH):

```powershell
$nssm = "C:\ORBIT\herramientas\nssm.exe"
& $nssm install ORBIT "C:\ORBIT\.venv\Scripts\python.exe" "serve.py"
& $nssm set ORBIT AppDirectory "C:\ORBIT"
& $nssm set ORBIT DisplayName "ORBIT Canella"
& $nssm set ORBIT Start SERVICE_AUTO_START
& $nssm set ORBIT ObjectName "CANELLA\svc_orbit" "<contraseña de la cuenta>"
& $nssm set ORBIT AppStdout "C:\ORBIT\logs\servicio.log"
& $nssm set ORBIT AppStderr "C:\ORBIT\logs\servicio.log"
& $nssm set ORBIT AppRotateFiles 1
& $nssm set ORBIT AppRotateBytes 10485760
Start-Service ORBIT
Invoke-WebRequest http://127.0.0.1:8000/salud
```

Los logs del hub siguen en `logs/` ([LOGS.md](LOGS.md)). `servicio.log` solo guarda lo que
salga por consola, como un error al arrancar.

## 3. IIS como proxy con HTTPS

1. Instalar IIS y los dos complementos de proxy:

   ```powershell
   Install-WindowsFeature Web-Server -IncludeManagementTools
   ```

   Descargar e instalar **URL Rewrite 2.1** y **Application Request Routing 3.0** de iis.net.

2. Activar el proxy de ARR: IP real sin puerto (Waitress no acepta `IP:puerto`) y 5 minutos de
   espera, porque una tarea lanzada desde un botón responde cuando termina:

   ```powershell
   $appcmd = "$env:windir\system32\inetsrv\appcmd.exe"
   & $appcmd set config -section:system.webServer/proxy /enabled:"True" /preserveHostHeader:"True" /includePortInXForwardedFor:"False" /timeout:"00:05:00" /commit:apphost
   & $appcmd set config -section:system.webServer/rewrite/allowedServerVariables /+"[name='HTTP_X_FORWARDED_PROTO']" /commit:apphost
   ```

3. Crear la carpeta del sitio con su `web.config`. El sitio no sirve archivos: solo reenvía.

   ```powershell
   New-Item -ItemType Directory -Force C:\inetpub\orbit
   ```

   `C:\inetpub\orbit\web.config`:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <configuration>
     <system.webServer>
       <rewrite>
         <rules>
           <rule name="HTTP a HTTPS" stopProcessing="true">
             <match url="(.*)" />
             <conditions><add input="{HTTPS}" pattern="off" /></conditions>
             <action type="Redirect" url="https://{HTTP_HOST}/{R:1}" redirectType="Permanent" />
           </rule>
           <rule name="ORBIT a Waitress" stopProcessing="true">
             <match url="(.*)" />
             <serverVariables><set name="HTTP_X_FORWARDED_PROTO" value="https" /></serverVariables>
             <action type="Rewrite" url="http://127.0.0.1:8000/{R:1}" />
           </rule>
         </rules>
       </rewrite>
       <security>
         <!-- 30 MB: por encima de SUBIDA_MAXIMA_MB (25), para que el 413 lo responda el hub en español -->
         <requestFiltering><requestLimits maxAllowedContentLength="31457280" /></requestFiltering>
       </security>
       <!-- Los errores (404, 413, 500...) y sus JSON los arma el hub; IIS no los reemplaza -->
       <httpErrors existingResponse="PassThrough" />
     </system.webServer>
   </configuration>
   ```

4. Crear el sitio con HTTPS (443) y HTTP (80, solo para redirigir):

   ```powershell
   Import-Module WebAdministration
   $nombre = "orbit.canella.com.gt"
   New-Website -Name ORBIT -PhysicalPath C:\inetpub\orbit -HostHeader $nombre -Port 80
   New-WebBinding -Name ORBIT -Protocol https -Port 443 -HostHeader $nombre -SslFlags 1
   $cert = Get-ChildItem Cert:\LocalMachine\My | Where-Object { $_.Subject -like "*$nombre*" } | Select-Object -First 1
   (Get-WebBinding -Name ORBIT -Protocol https).AddSslCertificate($cert.Thumbprint, "My")
   ```

   Si el sitio *Default Web Site* ocupa el puerto 80 sin nombre, no estorba: IIS elige el sitio
   por el nombre (`HostHeader`).

5. Firewall: abrir 80 y 443. **Nunca el 8000.**

   ```powershell
   New-NetFirewallRule -DisplayName "ORBIT HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
   New-NetFirewallRule -DisplayName "ORBIT HTTP (redirige)" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
   ```

## 4. Verificar

Desde otro equipo de la red:

| Prueba | Resultado esperado |
|---|---|
| `https://orbit.canella.com.gt/salud` | `{"estado":"ok"}` y candado sin advertencias |
| `http://orbit.canella.com.gt` | Redirige a `https://` |
| `http://<ip-del-servidor>:8000/salud` | No responde (el puerto no está abierto) |
| Iniciar sesión | Entra; en las herramientas del navegador la cookie `automate_canella_session` aparece con `Secure` y `HttpOnly` |
| Un intento fallido de login | El log `auth.fallido` / la tabla `HUB_INTENTOS_ACCESO` muestran la IP del equipo del usuario, no `127.0.0.1` |
| Una página inexistente | El 404 del hub, no la página de error de IIS |

## 5. Actualizar a una versión nueva

En el servidor, PowerShell como administrador:

```powershell
cd C:\ORBIT
.\scripts\actualizar.ps1
```

El script trae de GitHub **la rama en la que está la carpeta** (`main` en producción, `dev` en
pruebas) y hace, en orden:

1. Se niega a seguir si alguien editó archivos a mano en el servidor.
2. `git pull --ff-only`.
3. Detiene el servicio. En Windows no se puede reemplazar un paquete de Python que esté en uso.
4. `pip install` y `flask db upgrade`. Si no hay nada nuevo, no hacen nada.
5. Vuelve a arrancar el servicio, aunque un paso haya fallado, y espera a que `/salud` responda.

Si un paso falla, se detiene y dice cuál. Opciones: `-Servicio ORBIT` y
`-Salud http://127.0.0.1:8000/salud`.

Al reiniciar, las sesiones abiertas siguen valiendo porque `SECRET_KEY` no cambia. Una tarea
que esté corriendo en ese momento se corta y queda `interrumpida`
([EJECUCIONES.md](EJECUCIONES.md)). Conviene reiniciar fuera de horario.

**Volver atrás:** `git checkout <commit anterior>` y `Restart-Service ORBIT`. Si la versión
nueva traía migraciones, primero `flask --app wsgi db downgrade` hasta la revisión anterior.

## Ambiente de pruebas (128.1.200.70, rama `dev`, Caddy)

Es el mismo procedimiento, con tres diferencias: la rama es `dev`, la base es aparte y en lugar
de IIS se usa **Caddy**. Caddy es un solo `.exe`, se instala sin roles de Windows y genera su
propio certificado.

```
Navegador ──HTTPS 8443──▶ Caddy (certificado interno) ──HTTP 127.0.0.1:8000──▶ Waitress (serve.py)
```

**El ciclo de cada cambio:**

1. En tu equipo: `python -m pytest`, luego `git push origin dev`.
2. En 128.1.200.70: `cd C:\ORBIT` y después `.\scripts\actualizar.ps1`.
3. Probar en `https://128.1.200.70:8443`.
4. Cuando todo esté probado, `dev` se pasa a `main` para producción.

**El servidor 128.1.200.70 también aloja la base productiva AUTOMATE_CANELLA.** El hub de
pruebas no debe tocarla nunca: su `.env` apunta solo a `AUTOMATE_CANELLA_PRUEBAS`.

### Primera vez

1. **Base de pruebas** (SSMS): crear una base vacía; las tablas las crea el paso 5.

   ```sql
   CREATE DATABASE AUTOMATE_CANELLA_PRUEBAS COLLATE Modern_Spanish_CI_AS;
   ```

   Un usuario SQL con permisos `db_owner` **solo** en esa base, para que el hub pueda crear tablas.

2. **Acceso a GitHub de solo lectura.** Se genera una *deploy key* (una llave SSH del servidor
   que solo puede leer este repositorio):

   ```powershell
   ssh-keygen -t ed25519 -f $HOME\.ssh\orbit_deploy -N '""' -C "orbit-pruebas"
   Get-Content $HOME\.ssh\orbit_deploy.pub   # pegar en GitHub: repo → Settings → Deploy keys (sin permiso de escritura)
   git config --global core.sshCommand "ssh -i $($HOME -replace '\\','/')/.ssh/orbit_deploy"
   ```

3. **Instalar** como en el paso 1 de esta guía, pero con la rama `dev` y la URL SSH del repositorio:
   `git clone -b dev git@github.com:<org>/<repo>.git C:\ORBIT`.

4. **`.env` de pruebas**: como el de producción, con estos cambios:

   ```ini
   AUTOMATE_ENV=production
   DATABASE_URL=<cadena de AUTOMATE_CANELLA_PRUEBAS>
   HOST=127.0.0.1
   PORT=8000
   PROXY_CONFIABLE=127.0.0.1
   # Módulos sin efectos reales:
   CORTE_CAJA_MODO=simulacion
   ```

   El login sigue usando STOD real, solo para lectura: cada quien entra con su usuario de
   siempre. En **Expedientes**, el envío está en *modo prueba* por omisión. En ese modo todo
   correo va a `cajamauto2@canella.com.gt` con «[PRUEBA]» en el asunto
   ([PLAN_EXPEDIENTES_SEGUROS.md](PLAN_EXPEDIENTES_SEGUROS.md)). No hay que cambiarlo en pruebas.

5. **Tablas**: `.venv\Scripts\flask --app wsgi db upgrade`.

6. **Waitress como servicio**: igual que el paso 2 de esta guía, con el nombre de servicio `ORBIT`.

7. **Caddy**: descargar `caddy.exe` (Windows amd64) de caddyserver.com a `C:\ORBIT\herramientas\`
   y crear `C:\ORBIT\herramientas\Caddyfile`:

   ```
   https://128.1.200.70:8443 {
       tls internal
       reverse_proxy 127.0.0.1:8000
   }
   ```

   Caddy ya manda `X-Forwarded-For` y `X-Forwarded-Proto`, que es lo que espera `PROXY_CONFIABLE`.

   ```powershell
   & $nssm install ORBIT-Caddy "C:\ORBIT\herramientas\caddy.exe" "run --config C:\ORBIT\herramientas\Caddyfile"
   & $nssm set ORBIT-Caddy Start SERVICE_AUTO_START
   Start-Service ORBIT-Caddy
   New-NetFirewallRule -DisplayName "ORBIT pruebas" -Direction Inbound -Protocol TCP -LocalPort 8443 -Action Allow
   ```

8. **Verificar** con la tabla del paso 4, cambiando la dirección a `https://128.1.200.70:8443`.
   El navegador avisará que el certificado no es de confianza. En pruebas se acepta; para que no
   avise, se instala la raíz de Caddy en el equipo de quien prueba.

**Cuenta del servicio.** NSSM corre el servicio como `LocalSystem` si no se indica otra cuenta.
Así funciona todo menos las carpetas de red: los anexos de SAP de Expedientes y el destino del
corte de caja. Para probarlas, el servicio `ORBIT` debe correr con un usuario de dominio que
tenga acceso a esas carpetas: `& $nssm set ORBIT ObjectName "CANELLA\<usuario>" "<contraseña>"`.
TI puede crear uno propio para el hub.

**No crear en pruebas la tarea programada del corte de caja** mientras producción use el mismo
buzón.

## Las tareas programadas van aparte

Las corridas sin sesión web, como el corte de caja cada 5 minutos, no pasan por IIS ni por
Waitress. Se ejecutan con el Programador de tareas y la misma cuenta de servicio: ver
[EJECUCIONES.md](EJECUCIONES.md#sin-sesión-web-tareas-programadas) y la guía de cada módulo.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| 502.3 de IIS | El servicio ORBIT está detenido o escucha en otro puerto: `Get-Service ORBIT`, revisar `logs\servicio.log` |
| 502.3 después de ~5 minutos | Una tarea de botón tardó más que el `timeout` de ARR; subirlo o pasar la tarea a programada |
| El login entra y vuelve a pedir usuario | Se abrió por `http://` o sin el proxy: la cookie `Secure` solo viaja por HTTPS |
| 500.50 «URL Rewrite Module Error» | Falta permitir `HTTP_X_FORWARDED_PROTO` (paso 3.2) |
| Todos los intentos fallidos muestran `127.0.0.1` | Falta `PROXY_CONFIABLE=127.0.0.1` en `.env` o no se reinició el servicio |
| El servicio arranca y se detiene | Error de configuración (`SECRET_KEY`, `DATABASE_URL`): `logs\servicio.log` |
