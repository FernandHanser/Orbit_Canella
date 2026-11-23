# Plan de trabajo

Estado al 28/09/2026: **fases 1 y 3 implementadas**; la 3 falta ponerla en producción. Los
prototipos no se modificaron: Corte de caja se reescribió en el hub con su lógica de negocio.

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Acciones de seguridad urgentes | Pendiente (responsables fuera del hub) |
| 1 | Inicio de sesión con usuarios de STOD y roles del hub | **Implementada** (24/09/2026) |
| 1b | Base de datos `AUTOMATE_CANELLA` en SQL Server (tablas del núcleo `HUB_*`, de módulos `<ID_MODULO>_*`) | **Creada en 128.1.200.70 y conectada** (24/09/2026), con el login `usrsap` (provisional: tiene más permisos de los necesarios) → [scripts/sqlserver/](../scripts/sqlserver/README.md) |
| 2 | Piezas compartidas para los módulos | Diseñada |
| 3 | Módulo Corte de caja | **Implementado** (28/09/2026), 49 pruebas; migración aplicada en 128.1.200.70; leyendo el buzón real en modo simulación. Falta corrida en paralelo y corte → [PLAN_INTEGRACION_CORTE_DE_CAJA.md](PLAN_INTEGRACION_CORTE_DE_CAJA.md#paso-a-producción) |
| 5 | Módulo Expedientes de Seguros (Taller) | **Implementado** (28/09/2026), 35 pruebas, migración aplicada; falta prueba con llamada real → [PLAN_EXPEDIENTES_SEGUROS.md](PLAN_EXPEDIENTES_SEGUROS.md) |
| 4 | Módulo Contraseñas de pago | Diseñado → [PLAN_INTEGRACION_CONTRASENAS.md](PLAN_INTEGRACION_CONTRASENAS.md) |

## Decisiones tomadas

| Fecha | Decisión |
|---|---|
| 24/09/2026 | Todo usuario **activo en STOD** puede iniciar sesión en el hub con su usuario y contraseña de STOD. El hub no guarda contraseñas |
| 24/09/2026 | Dentro del hub, el acceso se administra **módulo por persona** (sin grupos de roles) |
| 24/09/2026 | Jerarquía: **superadministrador** (`fhanser`), administradores y usuarios |
| 24/09/2026 | La conexión a STOD usa **las mismas credenciales que CODA_REPORTS** (usuario de SQL `usrSTOD`) |
| 24/09/2026 | Orden: Corte de caja antes que Contraseñas |
| 28/09/2026 | Corte de caja: **el buzón es la cola** (subcarpetas `Procesados`/`Rechazados`/`Ignorados`/`Error`) en lugar de marca de agua |
| 28/09/2026 | Corte de caja: se **elimina la entrada por carpeta local** (ya no se usa) |
| 28/09/2026 | Corte de caja: solo se atiende a remitentes de **`@canella.com.gt`** (configurable) y se responde solo al remitente |
| 28/09/2026 | Núcleo: estado de ejecución **`sin_cambios`** con purga automática, para tareas programadas frecuentes |
| 28/09/2026 | Corte de caja: el **revisor de Contabilidad ve todas las empresas** (sin alcance por empresa) y **no configura** el módulo; las empresas las administra Informática (administradores del hub). Ver [GLOSARIO.md](GLOSARIO.md) |

---

## Fase 0 — Seguridad urgente

1. **Hacer privados** los repositorios `AUTOMATIZACION_CORTE_DE_CAJA_DIARIO` y
   `Automatizacion_Contrasenas` (hoy públicos en GitHub).
2. **Rotar la contraseña de la cuenta `itcanella`** (servidor de archivos .70). Está expuesta en:
   - `AUTOMATIZACION_CORTE_DE_CAJA_DIARIO`: `app/config.py` de `main` y dos commits del historial
     (repositorio público).
   - `CODA_REPORTS`: `.env.example` versionado con el valor real de `SMB_PASSWORD` (repositorio
     privado, pero queda en el historial).

   Tras rotarla, actualizar los `.env` de todos los sistemas que la usan.
3. **Cambiar la contraseña del panel** de Corte de caja (autenticación básica con valor por
   defecto en `run.py`; el panel parece publicarse con un túnel de Cloudflare).
4. **STOD como `sa`**: el README de Contraseñas lo documenta. Ese prototipo debe dejar de usar
   `sa`; en el hub se usará `usrSTOD` (decisión del 24/09).
5. **Defectos activos en el prototipo de Corte de caja** (encontrados el 28/09/2026, corregidos
   en el hub; avisar al responsable mientras el prototipo siga operando):
   - **Cortes perdidos**: si falla la red o la escritura de un adjunto, el correo no se reintenta
     porque la marca de agua avanza igual (`email_service.py`, líneas 372–418).
   - **Rechazo explotable**: el asunto se inserta sin escapar en el HTML del rechazo y se envía
     con `reply_all` a cualquier remitente, incluso externo. Alguien de fuera puede hacer que el
     buzón corporativo envíe su HTML a terceros en copia.

---

## Fase 1 — Inicio de sesión con usuarios de STOD

**Implementada el 24/09/2026**: `app/integraciones/stod.py`, `app/core/auth.py`, migración
`44af1c4cd376`, 65 pruebas con STOD simulado. `fhanser` designado superadministrador. Probado contra STOD real el
24/09/2026 (inicio de sesión de `fhanser`).

Replica el mecanismo de `CODA_REPORTS/security.py`, que ya funciona en producción, con los
ajustes de seguridad indicados.

### Cómo valida CODA (referencia)

- Base `STOD_SAPBONE` en `128.1.200.70`, tablas de **ASP.NET Membership**: `aspnet_Users` +
  `aspnet_Membership`.
- Usuario activo: `IsApproved = 1` y `IsLockedOut = 0`.
- Contraseña: `base64(SHA1(salt + contraseña en UTF-16LE)) == Password`, con el salt de
  `PasswordSalt` en base64.
- Roles de STOD (`aspnet_Roles`): solo se muestran; no controlan nada.

### Flujo en el hub

```text
Formulario (usuario STOD + contraseña)
  → límite de intentos del hub por usuario (no se escribe en STOD)
  → consulta a STOD: usuario activo y PasswordFormat = 1
  → verificación del hash (comparación en tiempo constante)
  → primer ingreso: se crea el usuario en el hub (rol "usuario", sin módulos)
  → usuario deshabilitado en el hub: no entra aunque esté activo en STOD
  → sesión
```

- **Revalidación**: cada 15 minutos, en la siguiente petición, se vuelve a comprobar en STOD que
  el usuario siga activo. Si ya no lo está, se cierra su sesión. Si STOD no responde en ese
  momento, la sesión continúa y se registra una advertencia (una caída de STOD no debe sacar a
  todos).
- **STOD caído al iniciar sesión**: mensaje "No se pudo validar con STOD, intenta en unos
  minutos". No hay contraseña local de respaldo.
- **Sin puertas traseras**: no se replica el `admin/admin` de desarrollo de CODA. Las pruebas
  automáticas usan un proveedor de identidad simulado, solo en el ambiente `testing`.

### Roles del hub

| Rol | Qué puede hacer | Cómo se asigna |
|---|---|---|
| **Superadministrador** | Todo lo del administrador, más nombrar y quitar administradores y administrar el catálogo de módulos | Por consola: `flask --app wsgi usuarios superadmin fhanser`. No se puede quitar desde la web |
| **Administrador** | Asignar y quitar módulos a las personas, habilitar o deshabilitar usuarios en el hub, ver ejecuciones y logs | Lo nombra un superadministrador |
| **Usuario** | Usar los módulos que tenga asignados | Automático en su primer ingreso |

Ningún rol da acceso implícito a los módulos: también al superadministrador hay que
asignárselos (igual que hoy).

### Cambios en el hub

| Área | Cambio |
|---|---|
| Modelo `Usuario` | Identidad por `usuario_stod` (único, en minúsculas) y `stod_user_id` (GUID). `email` y `nombre` se toman de STOD y se actualizan en cada ingreso. `es_admin` pasa a `rol` (`usuario`, `admin`, `superadmin`). Se elimina `password_hash`. Se agrega `stod_verificado_en` |
| Migración | Nueva migración Alembic. Los usuarios locales de prueba actuales (`fhanser@canella.com.gt`, `tu@canella.com.gt`) se eliminan; el superadministrador se registra por consola y se vincula en su primer ingreso |
| Login | Campo "Usuario STOD" en lugar de correo |
| Se elimina | Cambio de contraseña propia, restablecimiento por el administrador, reglas de contraseña local, `crear-admin` con contraseña y `AUTOMATE_ADMIN_PASSWORD` |
| Administración | Los usuarios aparecen al ingresar por primera vez (no se crean a mano). Se pueden **prerregistrar** por usuario STOD para asignarles módulos antes de su primer ingreso |
| Conexión | `app/integraciones/stod.py`: conexión y consultas a STOD, compartida con el módulo Contraseñas |
| Configuración | `STOD_SERVER`, `STOD_DATABASE`, `STOD_USERNAME`, `STOD_PASSWORD`, `STOD_ODBC_DRIVER` (por defecto `ODBC Driver 17 for SQL Server`), `STOD_REVALIDAR_MINUTOS` (15) |
| Dependencias | `pyodbc`; en el servidor, ODBC Driver 17 o 18 (este equipo tiene ambos) |
| Logs | Eventos `auth.*` con el usuario STOD; nunca la contraseña ni el hash |
| Pruebas | Proveedor simulado: usuario activo, inactivo, bloqueado, contraseña errónea, STOD caído, revalidación, primer ingreso, jerarquía de roles |
| Documentación | README (primer acceso), guías y `.env.example` |

### Verificaciones en STOD

Consultas de solo lectura ejecutadas en SSMS el 24/09/2026:

| Verificación | Resultado | Consecuencia |
|---|---|---|
| `PasswordFormat` en `aspnet_Membership` | Los 2,524 registros en `1` (hash) | Todos validan con SHA1 + salt; no hay casos en texto plano ni cifrados |
| Aplicaciones (`ApplicationName`) | Una sola: `/` (2,524 usuarios) | El nombre de usuario es único; no hace falta filtrar por aplicación |
| Usuario `fhanser` | `IsApproved = 1`, `IsLockedOut = 0`, formato `1` | Válido como superadministrador |

Pendiente:

- **Nombre completo**: `aspnet_Users` no lo tiene. Mientras no se defina otra fuente, se usa como
  CODA: la parte del correo antes de la @ (o el usuario STOD si no hay correo). Si STOD tiene una
  tabla de empleados o perfiles, se toma de ahí.

### Riesgos aceptados

- `usrSTOD` es el usuario de la aplicación STOD, con más permisos que los necesarios para leer
  dos tablas. Se acepta por ahora (decisión del 24/09). Recomendado a futuro: un login propio con
  `SELECT` solo sobre `aspnet_Users` y `aspnet_Membership`.
- El formato SHA1 de ASP.NET Membership es antiguo, pero es el de STOD; el hub solo lo lee.

---

## Fase 2 — Piezas compartidas para los módulos

Los dos prototipos repiten el mismo esqueleto con los mismos problemas para vivir en el hub:

| Aspecto | Hoy en los prototipos | En el hub |
|---|---|---|
| Ejecución | Hilos infinitos dentro del proceso web | Tareas del módulo ejecutadas por el **Programador de tareas** de Windows con `flask tareas ejecutar` |
| Carpeta de red | `net use` con usuario y contraseña | La cuenta de servicio que corre la tarea tiene permiso sobre la carpeta |
| Estado | JSON o SQLite propios | Tablas del módulo con migraciones |
| Logs | `basicConfig`, `print`, JSON para el panel | `get_logger("<modulo>")` + ejecuciones del núcleo |
| Panel | Flask propio sin login o con autenticación básica | Pantallas del módulo con el login del hub |
| Configuración | Defaults quemados en el código | Variables `<MODULO>_*` obligatorias en `.env` |

A construir:

1. ~~**Ejecución exclusiva de tareas**~~: hecho el 25/09/2026 (mutex por módulo; ver [EJECUCIONES.md](EJECUCIONES.md#ejecución-exclusiva-por-módulo)).
2. ~~**Servicio de correo compartido**~~: **no se hace todavía** (28/09/2026). Con EWS en Corte de
   caja y Graph en Contraseñas, el principio 5 de [ARQUITECTURA.md](ARQUITECTURA.md) pide no
   unificar. Cada módulo tiene su contrato `Buzon`; se unifican cuando TI decida la plataforma.
3. **Utilidades de archivos**: nombres seguros (sin `..`, separadores ni caracteres inválidos),
   nombre único, control de longitud de ruta.
4. **Conexión a STOD** (`app/integraciones/stod.py`), la misma de la fase 1.
5. **Dependencias por módulo**: `requirements-<modulo>.txt` para no instalar OCR si no se usa.
   Convención en uso desde el 28/09/2026 (`requirements-corte_caja.txt`).
6. **Permisos dentro de un módulo**: resuelto el 28/09/2026 para el caso común con
   `app/core/permisos.py` (acciones solo para administradores del hub). Corte de caja lo usa en
   el CRUD de empresas. Si algún día hace falta delegar la configuración de un módulo a alguien
   que no es administrador del hub, se evaluarán permisos finos por módulo.

### Decisiones pendientes con TI

1. **Plataforma de correo**: Corte de caja usa EWS con usuario y contraseña contra
   `owa.canella.com.gt`; Contraseñas usa Microsoft Graph. Confirmar dónde viven los buzones. En
   Exchange Online, EWS está en retiro (anunciado para octubre de 2026) y lo correcto es Graph
   con permisos de aplicación limitados a los buzones del robot.
2. **Buzones del robot**: Contraseñas lee hoy un buzón personal con inicio de sesión interactivo;
   proponer buzones compartidos (`cortes@`, `contrasenas@`).
3. **Servidor y cuenta de servicio** del hub y de las tareas, con acceso a las carpetas
   compartidas y a STOD.
4. **Publicación**: si el hub debe ser accesible fuera de la red y con qué control.

---

## Fases 3 y 4 — Módulos

- **Corte de caja** (`corte_caja`): reglas simples, sin dependencias pesadas, flujo maduro.
  Estrena las piezas compartidas. Detalle en [PLAN_INTEGRACION_CORTE_DE_CAJA.md](PLAN_INTEGRACION_CORTE_DE_CAJA.md).
- **Contraseñas de pago** (`contrasenas`): OCR, STOD y comprobante PDF; tiene más correcciones
  pendientes (nombres de adjuntos sin sanear, buzón personal, comportamiento ante fallas de
  STOD). Detalle en [PLAN_INTEGRACION_CONTRASENAS.md](PLAN_INTEGRACION_CONTRASENAS.md).

Repositorios analizados (rama `dev`, que es la vigente; `main` está desactualizada en ambos):
`RicardoCruzLemus/AUTOMATIZACION_CORTE_DE_CAJA_DIARIO` (21/09/2026) y
`RicardoCruzLemus/Automatizacion_Contrasenas` (24/09/2026).
