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
| Cuenta de servicio | Cuenta de dominio con la que corre el hub; necesita leer y escribir en las carpetas de red de los módulos | `CONSULTORIA\svc_orbit` |

---

## 1. Instalar el hub

1. Instalar **Python 3.13** (marcar «Add to PATH» e instalar para todos los usuarios) y el
   **ODBC Driver 17 o 18 for SQL Server**.
2. Clonar la rama `main` e instalar dependencias:

   ```powershell
   git clone -b main git@github.com:FernandHanser/Orbit_Canella.git C:\ORBIT
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
   icacls C:\ORBIT\.env /inheritance:r /grant:r "Administradores:F" "CONSULTORIA\svc_orbit:R"
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
& $nssm set ORBIT ObjectName "CONSULTORIA\svc_orbit" "<contraseña de la cuenta>"
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
4. `pip install` y migraciones (`flask db upgrade`). Si no hay nada nuevo, no hacen nada.
5. Vuelve a arrancar el servicio, aunque un paso haya fallado, y espera a que `/salud` responda.

Si un paso falla, se detiene y dice cuál. El servicio, los requirements, las migraciones y el
puerto los toma de `scripts/despliegue.psd1`; `-Servicio` y `-Salud` los cambian para una corrida.

Al reiniciar, las sesiones abiertas siguen valiendo porque `SECRET_KEY` no cambia. Una tarea
que esté corriendo en ese momento se corta y queda `interrumpida`
([EJECUCIONES.md](EJECUCIONES.md)). Conviene reiniciar fuera de horario.

**Volver atrás:** `git checkout <commit anterior>` y `Restart-Service ORBIT`. Si la versión
nueva traía migraciones, primero `flask --app wsgi db downgrade` hasta la revisión anterior.

## Ambiente de pruebas (128.1.200.70, rama `dev`, Caddy)

Corre la rama `dev` contra **la misma base que usa tu equipo**, con Caddy en lugar de IIS. El
Caddy del servidor es **uno solo, compartido** por todos los proyectos de prueba (`C:\Caddy`).
Cada proyecto agrega su sitio en su propio puerto, sin cortar a los demás. Lo instala
[`scripts/instalar_pruebas.ps1`](../scripts/instalar_pruebas.ps1), que es igual en todos los
proyectos (skill `caddy-deploy`). Lo propio de ORBIT está en
[`scripts/despliegue.psd1`](../scripts/despliegue.psd1).

```
Navegador ──HTTPS 8443──▶ Caddy compartido (C:\Caddy) ──HTTP 127.0.0.1:8000──▶ Waitress (servicio ORBIT)
```

**Puertos y Python se eligen solos.** Los puertos preferidos son 8000 (interno) y 8443
(público). Si alguno está ocupado, el instalador toma el siguiente libre y lo anota en
`C:\Caddy\sitios\orbit.caddy`, de donde lo lee `actualizar.ps1`. De Python usa el más nuevo
que cumpla 3.11, no el del PATH, que en el .70 es 3.10. Si el `.venv` tiene uno viejo, lo rehace.

### Primera vez

En el servidor tienen que estar **Python 3.11 o más nuevo** (mejor 3.13, para todos los usuarios),
**Git for Windows** y el **ODBC Driver 17 o 18 for SQL Server**.

1. Copia a una misma carpeta del servidor (p. ej. el escritorio, por escritorio remoto)
   `scripts\instalar_pruebas.ps1`, `scripts\despliegue.psd1` y el **`.env` de tu equipo**.
2. Abre PowerShell **como administrador** en esa carpeta:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\instalar_pruebas.ps1
   ```

3. Cuando muestre la llave, pégala en GitHub: *Orbit_Canella → Settings → Deploy keys → Add deploy
   key*, **sin** marcar *Allow write access*. Luego presiona Enter.
4. Al terminar, entra a la URL que imprime (`https://128.1.200.70:8443`) con tu usuario de STOD.
   El navegador avisará del certificado: en pruebas se acepta. Para quitar el aviso en un equipo, se instala
   `C:\Caddy\datos\pki\authorities\local\root.crt` en sus *Entidades de certificación raíz de
   confianza*.

Si algo falla, el script dice en qué paso. Se corrige y se vuelve a correr: salta lo que ya esté
hecho.

**Qué hace:** elige puertos y Python, clona `dev` en `C:\ORBIT`, crea el
`.venv` e instala dependencias. Copia el `.env` y le cambia solo lo de `Env` en
`despliegue.psd1`: `AUTOMATE_ENV=production`, `HOST=127.0.0.1`, `PORT=<interno elegido>`,
`PROXY_CONFIABLE=127.0.0.1`, `SESSION_COOKIE_SECURE=1` y `LOG_DIR` vacío, más un `SECRET_KEY`
si no tenía. (Corte de caja ya no tiene modo simulación: no programar su tarea en este servidor
mientras el prototipo siga leyendo el mismo buzón.) Aplica migraciones pendientes e
instala el servicio `ORBIT`. Si falta, instala el Caddy compartido (servicio `Caddy`). Luego
agrega el sitio `C:\Caddy\sitios\orbit.caddy`, recarga Caddy, abre el 8443 y comprueba `/salud`.
Si el servidor sale a internet por proxy: `-Proxy http://128.1.200.140:8080`.

### Cada cambio: automático con GitHub Actions

```
git push dev ──▶ GitHub Actions ──▶ 1. Pruebas (máquina Windows de GitHub)
                                    2. Si pasan: runner en 128.1.200.70 ──▶ actualizar.ps1 ──▶ /salud
```

1. En tu equipo: `git push origin dev`.
2. Nada más. En la pestaña **Actions** del repositorio se ve cada corrida: quién, qué commit, las
   pruebas, el despliegue y su log. Si las pruebas fallan, no se despliega.
3. Probar en `https://128.1.200.70:8443`.
4. Cuando todo esté probado, `dev` se pasa a `main` para producción.

El flujo está en [`.github/workflows/despliegue-pruebas.yml`](../.github/workflows/despliegue-pruebas.yml).
El paso del servidor corre `actualizar.ps1 -Commit <sha>`, que se niega a terminar si el servidor
no quedó en el commit probado. Para desplegar sin hacer push: *Actions → Pruebas y despliegue
(dev) → Run workflow*. A mano, en el servidor, sigue funcionando
`cd C:\ORBIT; .\scripts\actualizar.ps1`.

**El runner** es un agente de GitHub instalado como servicio en el servidor. Sale a GitHub por
HTTPS a buscar trabajo, así que no se abre ningún puerto. Corre como `LocalSystem` para poder
detener y arrancar el servicio `ORBIT`. Cualquiera con permiso de escritura en el repositorio puede
ejecutar código en el servidor a través de él: el repositorio debe seguir siendo privado y con
pocos colaboradores.

#### Instalar el runner (una vez)

En el servidor, PowerShell **como administrador**:

1. En GitHub: *Orbit_Canella → Settings → Actions → Runners → New self-hosted runner → Windows*.
   La página muestra los comandos con un token que vale una hora.
2. Corre los comandos de **Download** de esa página, pero en la carpeta `C:\actions-runner\orbit`
   en lugar de `C:\actions-runner` (un runner por proyecto).
3. Corre el `config.cmd` de la sección **Configure**, agregándole al final:

   ```powershell
   --name srv70-orbit --labels orbit-pruebas --runasservice --unattended
   ```

4. Pasa el servicio a `LocalSystem` y deja que git confíe en `C:\ORBIT`, que es de otro usuario:

   ```powershell
   $s = (Get-Service "actions.runner.*orbit*").Name; sc.exe config $s obj= LocalSystem; Restart-Service $s
   git config --system --add safe.directory C:/ORBIT
   ```

5. En GitHub, *Settings → Actions → Runners* debe mostrar `srv70-orbit` como **Idle**. Para la
   primera prueba: *Actions → Pruebas y despliegue (dev) → Run workflow*.

### Cuidado

- **La base es compartida** con tu equipo: lo que hagas en pruebas se ve en local y al revés.
  `actualizar.ps1` aplica las migraciones de `dev` a esa base, igual que `flask db upgrade` en
  tu equipo.
- **Carpetas de red.** El servicio `ORBIT` corre como `LocalSystem` y así no lee las carpetas de
  red: ni los anexos de SAP de Expedientes ni el destino del corte de caja. Para probarlas, ponle
  un usuario de dominio con acceso a ellas y dale lectura del `.env`:

  ```powershell
  C:\Caddy\nssm.exe set ORBIT ObjectName "CONSULTORIA\<usuario>" "<contraseña>"
  icacls C:\ORBIT\.env /grant "CONSULTORIA\<usuario>:R"
  Restart-Service ORBIT
  ```

- En Expedientes, el envío está en *modo prueba* por omisión: todo correo va a
  `cajamauto2@canella.com.gt` con «[PRUEBA]» en el asunto
  ([PLAN_EXPEDIENTES_SEGUROS.md](PLAN_EXPEDIENTES_SEGUROS.md)).
- **No crear en pruebas la tarea programada del corte de caja** mientras producción use el mismo
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
