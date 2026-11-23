# ORBIT Canella

**Hub de Automatizaciones de Contabilidad Canella.** Monolito modular en Flask que centraliza el
inicio de sesión, la asignación de permisos, el catálogo de módulos, el registro de ejecuciones
y los logs de las automatizaciones contables. Cada automatización es un **módulo** dentro de
`app/modulos/`; el núcleo (`app/core/`) resuelve todo lo común.

Los comandos de este documento son para **Git Bash** en Windows.

---

## Si eres nuevo en el proyecto

Lee en este orden (unos 30 minutos) y no hace falta más para empezar:

1. **Este README** hasta «Arquitectura»: arrancar el hub y por qué está hecho así.
2. **[docs/MAPA.md](docs/MAPA.md)**: qué pasa al arrancar, el recorrido de una petición y en qué
   archivo vive cada cosa.
3. **[docs/GLOSARIO.md](docs/GLOSARIO.md)**: el vocabulario (módulo, ejecución, actor…).
4. Según lo que vayas a hacer:

| Vas a… | Lee |
|---|---|
| Crear una automatización nueva | [AGREGAR_MODULO.md](docs/AGREGAR_MODULO.md) (y copia `app/modulos/ejemplo/`) |
| Tocar un módulo existente | Su guía (tabla «Guías», abajo) y el `__init__.py` del módulo |
| Tocar el núcleo (`app/core/`) | [ARQUITECTURA.md](docs/ARQUITECTURA.md) completo |
| Cambiar pantallas | [INTERFAZ.md](docs/INTERFAZ.md) |
| Escribir pruebas | [PRUEBAS.md](docs/PRUEBAS.md) |

**Ramas:** se trabaja en `dev`; `main` es lo que está en producción. Antes de subir cambios,
`python -m pytest` debe pasar completo (incluye las reglas de arquitectura).

---

## Arranque diario

Con el proyecto ya instalado (ver [Instalación](#instalación-primera-vez)):

```bash
cd "/d/Backup_CLOUD/OneDrive - Canella, S.A/GitHub/AUTOMATE_CANELLA"
source .venv/Scripts/activate
flask --app wsgi run --debug
```

- Abrir **http://127.0.0.1:5000** e iniciar sesión.
- Dejar la terminal abierta mientras se use; `Ctrl+C` lo detiene.
- `--debug` recarga el servidor al guardar un `.py` y las plantillas al instante. Si agregas una
  carpeta de módulo nueva, reinicia con `Ctrl+C` y vuelve a ejecutar el comando.
- Si falla con "Address already in use", ya hay otro servidor en el puerto 5000: ciérralo o usa
  `flask --app wsgi run --debug --port 5001`.

---

## Instalación (primera vez)

Requisitos: Python 3.11 o superior (probado con 3.13) y Git Bash.

```bash
cd "/d/Backup_CLOUD/OneDrive - Canella, S.A/GitHub/AUTOMATE_CANELLA"

# 1. Entorno virtual y dependencias
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements-dev.txt        # requirements.txt si no se van a correr pruebas
pip install -r requirements-corte_caja.txt # solo en el servidor que ejecuta ese módulo
pip install -r requirements-expedientes_seguros.txt # PDF y miniaturas (también lo instala requirements-dev)

# 2. Configuración local con una SECRET_KEY aleatoria
cp .env.example .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')/" .env

# 3. Base de datos: definir DATABASE_URL en .env (AUTOMATE_CANELLA en SQL Server,
#    ver scripts/sqlserver/README.md) y verificar el esquema
flask --app wsgi db upgrade
```

### Conexión a STOD y primer acceso

El inicio de sesión usa los **usuarios de STOD**: cualquier usuario activo en STOD entra con su
usuario y contraseña de STOD. El hub no guarda contraseñas.

1. Completar en `.env` las variables `STOD_SERVER`, `STOD_DATABASE`, `STOD_USERNAME` y
   `STOD_PASSWORD` (hoy se usan las mismas credenciales que CODA_REPORTS; pedirlas a
   Informática). El equipo necesita el **ODBC Driver 17 o 18 for SQL Server**.
2. Designar al superadministrador con su usuario de STOD (no pide contraseña):

   ```bash
   flask --app wsgi usuarios superadmin fhanser
   ```

3. Entrar en http://127.0.0.1:5000 con ese usuario de STOD (no el correo) y su contraseña de STOD.

Las demás personas quedan registradas en su primer ingreso, con rol **Operador** y sin módulos.
STOD no guarda nombres: al registrar o editar a una persona, **nombre y apellido son obligatorios**,
y es lo que se muestra en el sistema en lugar del usuario STOD. Quien entró sin prerregistro
aparece como «Sin nombre registrado» hasta que se complete.
Los administradores les asignan módulos en **Administración → Usuarios y permisos**, o las
registran antes de su primer ingreso con **Registrar usuario STOD**. Ningún rol da acceso
implícito a los módulos: también al superadministrador hay que asignárselos.

| Rol | Puede |
|---|---|
| Superadministrador | Todo, más nombrar o quitar administradores y administrar el catálogo de módulos. Se asigna solo por consola |
| Administrador | Asignar módulos, habilitar o deshabilitar usuarios, ver ejecuciones y logs |
| Operador | Usar los módulos asignados (rol técnico `usuario`) |

---

## Arquitectura: sobre qué estamos trabajando

El hub es un **monolito modular**: un solo despliegue, pero por dentro cada automatización es un
módulo aislado que depende únicamente del núcleo, y el núcleo no depende de ningún módulo ni
de ningún sistema externo concreto.

```text
modulos ──► core ◄── integraciones        (create_app los conecta)
```

Seguimos cinco principios, detallados con ejemplos del código en
[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md):

1. **Módulos tímidos:** cada módulo expone solo su `DefinicionModulo` y usa solo los servicios
   públicos del núcleo. No importa otros módulos ni los modelos ORM del núcleo.
2. **Inversión de dependencias:** el núcleo define contratos (por ejemplo, `core/identidad.py`)
   y las integraciones los implementan (STOD). Cambiar de proveedor no toca el núcleo.
3. **Sin ciclos de dependencias**, tampoco escondidos en imports dentro de funciones.
4. **Datos aislados:** tablas con prefijo por módulo, y entre límites solo DTOs inmutables
   (`ResumenEjecucion`, `Identidad`) o tipos simples, nunca filas ORM.
5. **Sin duplicación accidental:** no se unifica código solo porque se parezca; solo si cambia por
   el mismo motivo de negocio.

Cuando un módulo tenga que avisarle a otro, se hará con eventos en memoria (*signals* de Flask)
declarados en el núcleo, no con imports entre módulos.

**Por qué importa mantenerlo.** El hub va a crecer con una automatización tras otra. Mientras se
respeten estas reglas:

- Cada automatización se agrega, se prueba, se deshabilita o se reescribe sin romper las demás.
- Un cambio en el núcleo (login, base de datos, proveedor de identidad) no obliga a tocar cada
  módulo.
- Una persona nueva entiende un módulo leyendo solo su carpeta.
- Si algún día un módulo tiene que salir a su propio servicio, sus límites ya están trazados.

Cada excepción "por esta vez" acopla dos piezas, y ese acoplamiento se copia en todo módulo
nuevo que tome el anterior como plantilla. Por eso las reglas verificables están automatizadas:
`tests/test_arquitectura.py` falla si alguien las rompe. Si esa prueba falla, **se corrige el
diseño, no la prueba**.

La misma guía documenta la **atomicidad**: qué operaciones se aplican completas o no se aplican,
las reglas para las tareas (no hacer `commit` dentro de una tarea, efectos externos al final e
idempotentes) y los pendientes conocidos.

---

## Estructura

```text
app/
├── __init__.py           # create_app(): extensiones, logging, seguridad, Blueprints, módulos,
│                         #   helpers de plantilla (estatico, url_pagina) y manejo de errores
├── config.py             # configuración por ambiente (AUTOMATE_ENV); carga .env al importarse
├── extensions.py         # db, migrate, login_manager, csrf
├── core/                 # núcleo compartido (no lo modifican los módulos)
│   ├── auth.py           #   inicio de sesión con STOD, bloqueo por intentos, revalidación
│   ├── autorizacion.py   #   verificación central: sesión, rol admin y permiso por módulo
│   ├── permisos.py       #   contrato para módulos: acciones solo para administradores
│   ├── identidad.py      #   contrato del proveedor de identidad (lo implementa STOD)
│   ├── peticiones.py     #   utilidades de la petición HTTP (¿es API?, URL segura)
│   ├── admin.py          #   usuarios, permisos, catálogo, ejecuciones y logs
│   ├── hub.py            #   inicio con tarjetas y /salud
│   ├── registro.py       #   contrato DefinicionModulo y descubrimiento de módulos
│   ├── catalogo.py       #   sincronización código ↔ tabla modulos
│   ├── ejecuciones.py    #   registro común de ejecuciones (web, CLI, programadas)
│   ├── logs.py           #   logging central JSONL, saneamiento y búsqueda
│   ├── paginacion.py     #   paginación común (consultas y listas)
│   ├── seguridad.py      #   reglas de contraseña y cabeceras HTTP (CSP…)
│   ├── formularios.py    #   formularios Flask-WTF (con CSRF)
│   ├── sesion.py         #   vencimiento por inactividad y jornada
│   ├── roles.py          #   superadmin / admin / usuario
│   ├── migraciones.py    #   filtro de Alembic: nunca propone borrar tablas de otro módulo
│   ├── models.py         #   Usuario, IntentoAcceso, Modulo, PermisoModulo, Ejecucion
│   └── cli.py            #   comandos flask usuarios / modulos / tareas / logs
├── integraciones/        # sistemas externos compartidos
│   └── stod.py           #   conexión a STOD; implementa core/identidad (ASP.NET Membership)
├── modulos/              # una carpeta por automatización
│   ├── ejemplo/          #   módulo de EJEMPLO (plantilla de referencia, sin datos contables)
│   ├── corte_caja/       #   Corte de caja diario: buzón → validación → carpeta compartida
│   └── expedientes_seguros/ # Expedientes de Seguros: páginas del expediente en SAP → paquete → correo
├── templates/            # base_layout, base (con menú), base_publica (login), _macros,
│                         #   hub/, auth/, admin/, errores/
└── static/
    ├── css/automate.css  #   estilos propios
    ├── js/               #   interaccion (spinners, confirmaciones), sesion (aviso de
    │                     #   vencimiento), menu (ocultar menú), emblema del login
    ├── img/              #   logo, fondo del login y del sistema
    └── vendor/           #   Tabler, Tabler Icons, Oxanium, three.js, thinking-orbs (locales,
                          #   versión fijada: ver vendor/README.md)
migrations/               # Alembic (Flask-Migrate)
scripts/sqlserver/        # creación de la base del hub en SQL Server
docs/                     # guías (ver abajo)
tests/                    # pruebas automáticas (pytest)
wsgi.py                   # entrada para `flask --app wsgi` y servidores WSGI
serve.py                  # servidor Waitress para ambientes distintos a desarrollo
```

---

## Guías

| Guía | Para qué |
|---|---|
| [Mapa del código](docs/MAPA.md) | Arranque, recorrido de una petición, archivos de un módulo y dónde vive cada dato |
| [Fortalezas del hub](docs/FORTALEZAS.md) | Resumen de lo que el hub resuelve (arquitectura, interfaz, errores, logs, pruebas, sesión y autorización), dónde está y cómo se verifica |
| [Arquitectura](docs/ARQUITECTURA.md) | Principios del monolito modular, reglas de dependencias y atomicidad |
| [Glosario y actores](docs/GLOSARIO.md) | Vocabulario común y quién puede hacer qué en la plataforma y en cada módulo |
| [Pruebas automáticas](docs/PRUEBAS.md) | Qué son, tipos (integración, unitarias, arquitectura), qué cubren y qué no, cómo correrlas |
| [Agregar un módulo](docs/AGREGAR_MODULO.md) | Paso a paso y lista de verificación para una automatización nueva |
| [Interfaz](docs/INTERFAZ.md) | Plantillas, macros, estáticos, login y reglas de la CSP |
| [Logs centrales](docs/LOGS.md) | Cómo emitir y consultar logs identificados por módulo |
| [Ejecuciones y tareas programadas](docs/EJECUCIONES.md) | Registrar corridas y ejecutarlas sin sesión web |
| [Plan de trabajo](docs/PLAN_DE_TRABAJO.md) | Fases, decisiones tomadas, login con STOD, seguridad urgente y orden |
| [Expedientes de Seguros (Taller)](docs/PLAN_EXPEDIENTES_SEGUROS.md) | Módulo `expedientes_seguros`: datos en SAP, visor, paquete, correo y configuración |
| [Corte de caja diario](docs/PLAN_INTEGRACION_CORTE_DE_CAJA.md) | Módulo `corte_caja`: diseño, configuración, tarea programada y paso a producción |
| [Plan: Contraseñas de pago](docs/PLAN_INTEGRACION_CONTRASENAS.md) | Análisis y diseño del módulo `contrasenas` (no ejecutado) |

---

## Comandos

Todos con el entorno activado (`source .venv/Scripts/activate`):

| Comando | Uso |
|---|---|
| `flask --app wsgi run --debug` | Servidor de desarrollo en http://127.0.0.1:5000 |
| `flask --app wsgi usuarios listar` | Usuarios, rol, estado y módulos |
| `flask --app wsgi usuarios superadmin <usuario_stod>` | Designar superadministrador |
| `flask --app wsgi usuarios quitar-superadmin <usuario_stod>` | Pasarlo a administrador (debe quedar al menos uno) |
| `flask --app wsgi modulos listar` | Módulos registrados en código |
| `flask --app wsgi modulos sincronizar` | Crea/actualiza el catálogo en la BD (también ocurre al arrancar) |
| `flask --app wsgi tareas listar` | Tareas ejecutables sin sesión web |
| `flask --app wsgi tareas ejecutar <modulo> <tarea> --proceso <nombre> [--param k=v]` | Ejecuta una tarea. Salida: 0 bien, 1 error, 3 omitida porque el módulo ya tenía una en curso, 4 omitida porque el módulo está deshabilitado |
| `flask --app wsgi tareas interrumpidas [--horas N]` | Marca como `interrumpida` las ejecuciones colgadas en `en_curso` (también se hace al arrancar) |
| `flask --app wsgi tareas purgar [--dias N]` | Borra las ejecuciones `sin_cambios` antiguas (también se hace al arrancar) |
| `flask --app wsgi corte_caja empresas` | Empresas del corte de caja; `empresa-agregar` y `empresa-modificar` para cambiarlas |
| `flask --app wsgi logs buscar --modulo <id> --ejecucion <id> --nivel WARNING --dias 7` | Consulta el log central |
| `flask --app wsgi db migrate -m "mensaje"` | Genera una migración tras cambiar modelos |
| `flask --app wsgi db upgrade` | Aplica las migraciones pendientes |
| `python -m pytest` | Corre todas las pruebas (ver [PRUEBAS.md](docs/PRUEBAS.md)) |

---

## Configuración

Se lee de variables de entorno o del archivo `.env` (no versionado; plantilla en
`.env.example`). Una variable vacía equivale a no definida.

| Variable | Por defecto | Descripción |
|---|---|---|
| `AUTOMATE_ENV` | `development` | `development` o `production` (`testing` lo usan las pruebas) |
| `SECRET_KEY` | — | Obligatoria en producción. En desarrollo, si falta, se genera una temporal |
| `STOD_SERVER`, `STOD_DATABASE`, `STOD_USERNAME`, `STOD_PASSWORD` | — (base `STOD_SAPBONE`) | Conexión a STOD para el inicio de sesión |
| `STOD_ODBC_DRIVER` | `ODBC Driver 17 for SQL Server` | Driver ODBC instalado en el equipo |
| `STOD_REVALIDAR_MINUTOS` | 15 | Cada cuánto se comprueba que una sesión abierta siga activa en STOD |
| `DATABASE_URL` | — (obligatoria) | `AUTOMATE_CANELLA` en SQL Server: ver [scripts/sqlserver/README.md](scripts/sqlserver/README.md) |
| `EJECUCIONES_INTERRUMPIDAS_HORAS` | 2 | Al arrancar, las ejecuciones `en_curso` más antiguas se marcan `interrumpida`. Mayor que la tarea más larga |
| `EJECUCIONES_SIN_CAMBIOS_DIAS` | 7 | Días que se conservan las ejecuciones `sin_cambios` (corridas programadas sin nada que procesar) |
| `EXPEDIENTES_*` | — | Módulo Expedientes de Seguros: ver [PLAN_EXPEDIENTES_SEGUROS.md](docs/PLAN_EXPEDIENTES_SEGUROS.md#configuración) |
| `CORTE_CAJA_*` | — | Módulo Corte de caja: ver [PLAN_INTEGRACION_CORTE_DE_CAJA.md](docs/PLAN_INTEGRACION_CORTE_DE_CAJA.md#configuración) |
| `SUBIDA_MAXIMA_MB` | 25 | Tope de tamaño de cualquier petición, para todo el hub (413 «Archivo demasiado grande») |
| `SESSION_COOKIE_SECURE` | 0 en dev, 1 en prod | Requiere HTTPS cuando vale 1 |
| `SESION_INACTIVIDAD_MINUTOS` / `SESION_MAXIMA_HORAS` | 60 / 10 | Cierre por inactividad y por jornada máxima (ver [INTERFAZ.md](docs/INTERFAZ.md#expiración-de-la-sesión)) |
| `SESION_AVISO_SEGUNDOS` | 120 | Antelación del aviso «Tu sesión está por vencer» |
| `LOGIN_MAX_INTENTOS` / `LOGIN_BLOQUEO_MINUTOS` | 5 / 15 | Bloqueo en el hub tras intentos fallidos (no afecta la cuenta en STOD) |
| `LOG_DIR`, `LOG_LEVEL`, `LOG_RETENCION_DIAS`, `LOG_CONSOLA`, `LOG_ARCHIVO` | ver [LOGS.md](docs/LOGS.md) | Logs |
| `AUTOMATE_MODULOS` | todos | Lista de módulos a cargar, p. ej. `app.modulos.ejemplo` |
| `HOST` / `PORT` | 127.0.0.1 / 8000 | Solo para `serve.py` |

### Otros ambientes

```bash
AUTOMATE_ENV=production python serve.py      # Waitress, compatible con Windows
```

En `production`, `SECRET_KEY` es obligatoria y la cookie de sesión es `Secure`, así que se
necesita HTTPS (IIS o Nginx como proxy inverso). Para probar en HTTP local:
`SESSION_COOKIE_SECURE=0`.

---

## Seguridad (resumen)

- Identidad y contraseñas en STOD: el hub solo lee `aspnet_Users` y `aspnet_Membership` y
  compara el hash en tiempo constante. Bloqueo temporal por usuario e IP tras intentos fallidos.
- Cada 15 minutos se comprueba que el usuario siga activo en STOD; si no, se cierra su sesión.
- La sesión vence tras **60 minutos sin actividad** o **10 horas** desde el inicio, con aviso 2 minutos antes
  («Extender sesión») y el motivo en el login ([INTERFAZ.md](docs/INTERFAZ.md#expiración-de-la-sesión)).
- Cookie de sesión `HttpOnly`, `SameSite=Lax`, `Secure` en producción. Deshabilitar a un usuario
  o cambiar su rol cierra sus sesiones abiertas.
- CSRF en todos los formularios y en `POST/PUT/PATCH/DELETE` de las APIs (cabecera
  `X-CSRFToken`). Cierre de sesión solo por POST.
- **Autorización central en el servidor** (`app/core/autorizacion.py`): toda ruta exige sesión;
  `/admin` exige rol de administrador; cualquier ruta web o API bajo `/m/<modulo>` exige que el
  módulo esté habilitado y asignado al usuario, aunque la URL se escriba directamente.
- CSP estricta (`script-src 'self'`: sin JavaScript inline), `X-Frame-Options: DENY`, `nosniff`
  y `Cache-Control: no-store`. Todos los recursos se sirven localmente, sin CDN.

---

## Decisiones pendientes

- **Servidor de la base productiva**: los scripts para SQL Server están listos y probados
  ([scripts/sqlserver/](scripts/sqlserver/README.md)); falta definir en qué servidor se crea.
- **Servidor y HTTPS**: dónde se aloja el hub (Windows Server/IIS, contenedor…) y el certificado.
- **Autenticación corporativa**: si se integrará con Active Directory / Microsoft Entra ID; el
  login local está aislado en `core/auth.py`.
- **Cola de tareas**: no se incluye; ver el punto de conexión en [EJECUCIONES.md](docs/EJECUCIONES.md).
