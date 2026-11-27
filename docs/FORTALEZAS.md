# Fortalezas de la arquitectura de ORBIT Canella

Qué resuelve el hub por sí mismo, para que cada automatización contable se concentre en su
negocio. Cada punto dice **dónde está** y **cómo se verifica**. Estado al 28/09/2026: 3 módulos,
**194 pruebas automáticas que pasan en 16 segundos**.

> En una frase: un solo despliegue, pero cada automatización es una pieza aislada que hereda login,
> permisos, sesión, logs, ejecuciones, manejo de errores e interfaz sin escribir una línea de eso.

---

## 1. Monolito modular con reglas que se verifican solas

| Fortaleza | Dónde | Cómo se verifica |
|---|---|---|
| **Un módulo = una carpeta.** Se descubre al arrancar, monta sus rutas en `/m/<id>`, entra al catálogo y queda protegido. No se toca el núcleo | `app/core/registro.py`, `app/modulos/<id>/` | Módulos `ejemplo`, `corte_caja` y `expedientes_seguros` |
| **Dependencias en una sola dirección:** `modulos → core ← integraciones` | `docs/ARQUITECTURA.md` | `tests/test_arquitectura.py` falla si el núcleo importa un módulo, si un módulo importa a otro o a los modelos del núcleo, o si hay ciclos (también dentro de funciones) |
| **Contratos pequeños entre capas.** El módulo solo usa `DefinicionModulo`, `ejecucion`/`ejecutar_tarea`, `ResumenEjecucion`, `get_logger`, `es_administrador`/`solo_administradores` | `docs/ARQUITECTURA.md` | Prueba de arquitectura |
| **Inversión de dependencias.** El núcleo define el contrato de identidad y STOD lo implementa: cambiar a Entra ID no toca el núcleo | `core/identidad.py`, `integraciones/stod.py` | Las pruebas usan un proveedor simulado sin tocar el núcleo |
| **DTOs inmutables entre límites** (`ResumenEjecucion`, `Identidad`, `Llamada`…), nunca filas ORM | `core/ejecuciones.py` | Revisión de diseño + prueba de arquitectura |
| **Datos aislados por prefijo:** `HUB_*` del núcleo, `<MODULO>_*` de cada módulo | Modelos y migraciones | `tests/test_arquitectura.py`: prefijo por dueño y ningún módulo nombra tablas `HUB_*` |
| **Convivencia: un módulo no toca lo de otro ni lo de todos.** No lo nombra (tablas, `.env`, tareas, rutas, carpetas), no cambia `ruta`/`permiso`, no registra ganchos globales ni modifica `app.config`/`os.environ` | `docs/ARQUITECTURA.md` (principio 7) | `tests/test_arquitectura.py` y `DefinicionModulo` al arrancar |
| **Todo módulo queda probado en su acceso sin escribir nada:** cada ruta pide sesión, da 403 sin asignación y 503 deshabilitado; y `tests/test_<id>.py` es obligatorio | `tests/test_contrato_modulos.py` | Recorre las rutas que el hub descubre, también las de un módulo nuevo |
| **Un módulo defectuoso no tumba el hub:** si falla al importarse, se registra y el resto sigue | `cargar_modulos` | Log `modulo.error_carga` |
| **Sistemas externos detrás de un contrato del módulo** (buzón EWS, SAP): en pruebas se reemplazan por dobles | `corte_caja/buzon.py`, `expedientes_seguros/sap.py` | `BuzonFalso`, `SapFalso` |

## 2. Cómo se integra un módulo de automatización

### Qué escribe el módulo y qué le da el hub

| El módulo escribe | El hub le da sin escribir nada |
|---|---|
| Su **lógica de negocio** (reglas, cálculos, validaciones) en funciones puras y probables | Login con STOD, sesión y su expiración, revalidación |
| Sus **pantallas** extendiendo `base.html` con las macros del sistema de diseño | Menú, tarjeta en el inicio con la última ejecución, estilos, spinners y confirmaciones |
| Sus **tablas** (`<MODULO>_*`) y su migración | Autorización de todas sus rutas, API e imágenes; página de acceso denegado |
| Sus **tareas** (`tareas={"procesar": procesar}`) | Registro de cada ejecución, exclusividad, colgadas, `sin_cambios`, códigos de salida para el Programador de tareas |
| Un **contrato** para cada sistema externo (buzón, SAP) y su adaptador | Logs correlacionados por ejecución, saneados y consultables |
| Su `DefinicionModulo` (id, nombre, ícono, blueprint) | Catálogo: habilitar o deshabilitar (pantallas **y** tareas) y asignar por persona |

### Pasos (detalle en `AGREGAR_MODULO.md`)

```text
app/modulos/<id>/
├── __init__.py      MODULO = DefinicionModulo(id, nombre, descripcion, icono, blueprint, tareas)
├── reglas.py        negocio puro (sin Flask, sin base, sin red): lo más probado
├── servicios.py     casos de uso y tareas (ctx de ejecución, sin commit)
├── <sistema>.py     contrato Protocol + adaptador real (EWS, SAP…) → doble en pruebas
├── views.py         pantallas (sin decoradores de seguridad: los pone el núcleo)
├── models.py        tablas <ID>_*   +  migración con DATOS_INICIALES
└── templates/<id>/  extienden base.html
```

Se reinicia el servidor y el módulo **aparece en el catálogo**, protegido, con su tarjeta. Se asigna
a las personas y está en uso.

### Por qué esta arquitectura conviene a las automatizaciones

| Necesidad típica de una automatización contable | Cómo la resuelve el hub |
|---|---|
| **Correr sola** cada pocos minutos o cada día | Tarea declarada + Programador de tareas de Windows; exclusiva, registrada y con códigos de salida |
| **No duplicar ni perder** (correos, archivos, registros) cuando algo falla a mitad | Reglas de atomicidad: efectos al final e idempotentes, aislamiento por elemento, reversión en la base |
| **Probar contra el sistema real sin afectarlo** | Modo simulación (Corte de caja leyó el buzón real sin responder ni mover) |
| **Saber qué pasó** sin entrar al servidor | Ejecución con estado, resultado y traza + logs correlacionados; la tarjeta del inicio muestra si el robot sigue vivo |
| **Apagarla de inmediato** si se comporta mal | Deshabilitarla en el catálogo detiene pantallas, API y tareas programadas |
| **Integrar sistemas externos** (SAP, STOD, Exchange, carpetas de red) sin acoplarse | Contrato en el módulo, adaptador intercambiable, doble en pruebas; configuración por `.env` |
| **Que la opere Contabilidad** y la configure Informática | Permisos por persona y por módulo; configuración solo para administradores |
| **Crecer sin que una rompa a otra** | Aislamiento verificado por pruebas; un módulo defectuoso no tumba el hub |

**Evidencia:** los dos módulos reales se integraron así.
- **Corte de caja:** un prototipo con hilos infinitos, JSON y contraseñas en el código pasó a ser una tarea
  programada, con tablas, simulación, correcciones de seguridad y 50 pruebas.
- **Expedientes de Seguros:** integra SAP y el servidor de archivos, PDF, un checklist por aseguradora
  y correo, con 35 pruebas.

Ninguno de los dos requirió cambiar el login, los permisos, los logs ni la sesión.

## 3. Interfaz: sistema de diseño con diseño atómico

Tabler 1.5.1 e íconos locales, **sin CDN**. Un módulo compone pantallas con piezas del núcleo en
lugar de inventar las suyas.

| Nivel | Piezas del hub | Dónde |
|---|---|---|
| **Átomos** | Etiquetas de estado con **colores por significado** (verde bien, amarillo revisar, rojo falló, gris neutro, azul en curso), íconos, avatar con iniciales y color fijo por persona | `_macros.html`, `INTERFAZ.md` |
| **Moléculas** | `campo`, `interruptor`, `encabezado`, `paginacion`, `estado_ejecucion`, `avatar_persona`; **spinner** (`data-cargando`) y **confirmación** (`data-confirmar`, con condición `data-confirmar-si`) activados con atributos, sin JavaScript en el módulo | `_macros.html`, `static/js/interaccion.js` |
| **Organismos** | Menú lateral según permisos, tarjeta de módulo con última ejecución, modal de confirmación compartido, modal de expiración de sesión, tablas paginadas | `base.html`, `hub/inicio.html` |
| **Plantillas** | `base.html` (con sesión), `base_publica.html` (login y errores), páginas de error | `app/templates/` |

Además:

- **CSP estricta:** sin JavaScript inline; cada comportamiento vive en un archivo.
- **Estáticos versionados** (`estatico()`): al reemplazar un archivo, el navegador baja el nuevo sin Ctrl+F5.
- **Paginación de 15** en todas las listas, con una constante única (`core/paginacion.py`).
- **Principios de usabilidad aplicados y probados:** spinner en toda acción lenta; modal solo en
  acciones irreversibles o hacia terceros, con el foco en *Cancelar*; el texto dice qué va a pasar.
  `tests/test_interfaz.py` falla si alguien los quita.

## 4. Manejo de errores

| Situación | Qué ve la persona | Qué queda registrado | Dónde |
|---|---|---|---|
| Error inesperado en cualquier pantalla | «Error interno. Quedó registrado para su revisión.» Nunca una traza | `app.error` con la traza, el módulo y el usuario; la transacción se revierte | `app/__init__.py` |
| Ruta inexistente / sin permiso / módulo deshabilitado | Páginas propias: no encontrado, acceso denegado, módulo no disponible | `acceso.denegado`, `modulo.no_disponible` | `errores/*.html`, `core/autorizacion.py` |
| Cualquier error en la API | JSON con código (`401`, `403`, `404`, `409`, `503`) y mensaje | Igual que en web | `core/peticiones.py` decide web o API |
| Formulario enviado con la sesión vencida | Login con «Tu sesión había vencido cuando enviaste el formulario» (antes: «400 Bad Request») | `auth.formulario_sesion_vencida` | Manejador de `CSRFError` |
| Sistema externo caído (STOD, SAP, buzón) | Mensaje claro y la pantalla sigue funcionando (por ejemplo, la bandeja de Expedientes avisa y el buscador sigue) | Evento propio del módulo | Cada módulo |
| Falla dentro de una tarea | La ejecución queda en `error` con su traza; los cambios en la base se revierten | `ejecucion.error` | `core/ejecuciones.py` |
| Falla de un elemento en una tarea por lotes | Ese elemento queda en error y la tarea sigue con los demás (`advertencia`) | Fila del elemento + log | Regla 5 de atomicidad |

## 5. Logs centrales

| Fortaleza | Dónde |
|---|---|
| **Un solo formato para todo:** JSONL diario con fecha, nivel, **módulo**, **evento** estable, usuario, **ejecución** y datos | `core/logs.py`, `LOGS.md` |
| **Correlación automática:** todo lo que ocurre durante una ejecución lleva su `ejecucion_id`, también lo de bibliotecas externas | `core/ejecuciones.py` |
| **Saneamiento:** se ocultan contraseñas, tokens y cookies, y se recortan valores largos | Formateador de logs |
| **Consulta en pantalla** (Administración → Logs, con filtros) y por consola (`flask logs buscar`) | `core/admin.py`, `core/cli.py` |
| **Sin ruido:** los accesos HTTP de estáticos no llegan al archivo; retención configurable por ambiente | `LOGS.md` |
| **Auditoría:** cambios de permisos, roles, empresas, aseguradoras y checklists quedan con quién y qué cambió (antes/después) | Eventos `admin.*`, `corte_caja.*`, `expedientes.*` |

## 6. Ejecuciones y tareas programadas

| Fortaleza | Dónde |
|---|---|
| **Registro común** de cada corrida (web, API o Programador de tareas): quién, cuándo, estado, resultado y error | `core/ejecuciones.py`, `EJECUCIONES.md` |
| **Ejecución exclusiva por módulo** garantizada por la base (índice único filtrado), también ante dos procesos simultáneos | `HUB_EJECUCIONES` |
| **Ejecuciones colgadas** (servidor reiniciado) se marcan `interrumpida` al arrancar | `marcar_interrumpidas` |
| **Estado `sin_cambios`** para tareas que corren cada pocos minutos, con purga automática: el historial no se llena de corridas vacías | `purgar_sin_cambios` |
| **Deshabilitar un módulo detiene también sus tareas programadas** (salida 4), sin tocar Windows | `ejecutar_tarea` |
| **Códigos de salida** que el Programador de tareas distingue: 0 bien, 1 error, 3 ya había una en curso, 4 módulo deshabilitado | `core/cli.py` |
| **Atomicidad documentada:** sin `commit` dentro de tareas; efectos externos al final e idempotentes; aislamiento por elemento | `ARQUITECTURA.md#atomicidad` |

## 7. Personas, sesión y autorización

### Ciclo de vida de una persona

```text
Alta              Cualquier persona activa en STOD entra con su usuario y contraseña de STOD.
                  En su primer ingreso queda registrada como Operador, sin módulos.
                  O un administrador la registra antes («Registrar usuario STOD»): se valida que
                  exista en STOD, con nombre y apellido obligatorios, su rol y sus módulos.
Nombre            STOD no guarda nombres: se registran en el hub (nombres, apellidos) y es lo que
                  se muestra en todo el sistema, con avatar de iniciales. STOD nunca lo sobrescribe.
Permisos          Módulo por módulo y por persona (no hay acceso implícito por rol).
Rol               Operador → Administrador (solo el superadministrador, con confirmación);
                  Superadministrador solo por consola.
Uso               Cada 15 min se revalida en STOD. La sesión vence por inactividad (60 min)
                  o jornada (10 h), con aviso previo.
Baja              En STOD: pierde el acceso en ≤15 min. En el hub: «Deshabilitado» cierra sus
                  sesiones al instante; su historial (ejecuciones, logs, paquetes) se conserva.
```

| Fortaleza | Por qué importa |
|---|---|
| **Una sola identidad** (la de STOD); el hub no guarda contraseñas | No hay otra clave que olvidar ni que se pueda filtrar desde el hub |
| **Alta sin fricción y segura:** entra cualquiera de STOD, pero sin módulos | Nadie ve nada que no se le asignó |
| **Prerregistro:** se asignan módulos antes de su primer ingreso | La persona entra y ya encuentra sus automatizaciones |
| **Baja automática desde STOD** + deshabilitar en el hub | La salida de alguien de la empresa se refleja sola; no quedan accesos huérfanos |
| **Jerarquía protegida:** nadie se deshabilita ni se cambia el rol a sí mismo; un administrador no toca al superadministrador; debe quedar al menos un superadministrador | Evita quedarse sin administración o escalar privilegios |
| **Auditoría:** alta, cambios de rol, de estado y de módulos quedan en el log con quién lo hizo | Se puede responder «¿quién le dio acceso a X?» |
| **Lista con estado claro:** rol, habilitado o «Sin ingresar», «Sin nombre registrado», módulos, último acceso | Administración de un vistazo |

### Sesión y autorización

| Fortaleza | Dónde |
|---|---|
| **Login con STOD** (usuarios reales de Canella); **el hub no guarda contraseñas** | `core/auth.py`, `integraciones/stod.py` |
| **Bloqueo por intentos fallidos** por usuario e IP, sin escribir en STOD | `core/auth.py` |
| **Revalidación en STOD cada 15 min:** quien deja de estar activo pierde la sesión; si STOD cae, no se saca a todos | `revalidar_sesion` |
| **Expiración de sesión:** 60 min de inactividad y 10 h de jornada; aviso 2 min antes con *Extender sesión*, sincronizado entre pestañas; login con el motivo y regreso a la misma página | `core/sesion.py`, `static/js/sesion.js` |
| **Autorización central en el servidor** antes de cualquier vista: sesión, rol de administración y permiso del módulo, también para la API y las imágenes. Ocultar un botón no es la seguridad | `core/autorizacion.py` |
| **Denegar por defecto:** una persona nueva entra como Operador y sin módulos; ningún rol da acceso implícito a un módulo | `GLOSARIO.md` |
| **Roles con una sola fuente** (nombre, descripción y color), validados en el servidor | `core/roles.py` |
| **Permisos dentro de un módulo** (configurar vs operar) con un contrato del núcleo, sin decoradores propios | `core/permisos.py` |
| **Escalar privilegios pide confirmación** (dar el rol de Administrador) | `usuario_form.html` |
| **Deshabilitar a alguien o cambiarle el rol cierra sus sesiones** abiertas al instante | `version_sesion` |
| **Cabeceras de seguridad:** CSP, `X-Frame-Options`, `nosniff`, `no-store`; CSRF en formularios y API; cookie `HttpOnly`, `SameSite`, `Secure` en producción | `core/seguridad.py` |

## 8. Pruebas automáticas

**298 pruebas, menos de un minuto**, sin tocar nada real: base SQLite en memoria y STOD, SAP y
buzón simulados. Además, **13 de punta a punta** en un navegador real (`--e2e`), aparte.

| Archivo | Pruebas | Qué cubre |
|---|---|---|
| `test_acceso.py` | 68 | Login con STOD (casos de falla, bloqueo, revalidación), permisos por módulo, roles, nombres, administración, CSRF y cabeceras |
| `test_corte_caja.py` | 50 | Reglas del corte, archivador idempotente, tarea con buzón simulado, simulación, panel, CRUD de empresas |
| `test_expedientes_seguros.py` | 80 | Reglas, PDF, visor, bandeja, paquete, correo `.eml`, checklist, retención, permisos, aseguradoras |
| `test_logs_ejecuciones.py` | 41 | Logs, saneamiento, ejecuciones, reversión, interrumpidas, sin cambios, exclusividad, módulo deshabilitado |
| `test_sesion.py` | 9 | Inactividad, jornada, motivo, aviso, extender, API y formulario vencido con CSRF activo |
| `test_interfaz.py` | 17 | Spinners, confirmaciones, tarjetas del inicio y avatares en las pantallas clave |
| `test_arquitectura.py` | 12 | Las reglas del monolito modular: dependencias, ciclos, tablas, plantillas, convivencia entre módulos y que cada módulo tenga sus pruebas |
| `test_contrato_modulos.py` | 5 | Acceso de **todas** las rutas de cada módulo: sin sesión, sin asignación y deshabilitado |
| `test_scripts.py`, `test_migraciones.py`, `test_servidor.py` | 16 | Scripts de despliegue, filtro de migraciones y Waitress detrás de un proxy |
| `e2e/` (con `--e2e`) | 14 | Navegador real (Playwright): login, confirmaciones (también al eliminar una tienda del directorio), aviso de sesión, rol de Administrador, encabezados en celular |

Tipos: mayoría **de integración** (login, permisos, módulos y base funcionando juntos), **unitarias**
para las reglas puras (fechas, nombres de archivo, plantillas), **de arquitectura** y **de punta a punta**
(servidor de QA sin el `.env` real; para una revisión completa, el skill `qa-orbit` de Claude Code). Los cambios
de esquema se prueban además a mano en **SQL Server LocalDB** (subir, bajar, `db check` y el script
SQL). Regla: si falla la prueba de arquitectura, se corrige el diseño, no la prueba. Ver `PRUEBAS.md`.

## 9. Base de datos y despliegue

| Fortaleza | Dónde |
|---|---|
| **Migraciones versionadas** (Alembic); cada una probada en SQLite y SQL Server LocalDB en las dos direcciones antes de aplicarla | `migrations/` |
| **Datos iniciales con una sola fuente** (`DATOS_INICIALES` / `SQL_INICIAL` en la migración), reutilizados por el script de creación de la base | `scripts/sqlserver/generar_esquema.py` |
| **Script SQL para el DBA** que crea la base completa en SSMS, sin Python | `scripts/sqlserver/02_esquema.sql` |
| **Compatibilidad SQL Server documentada** (índices filtrados, booleanos, cascadas, `DEFAULT` al borrar columnas) | `scripts/sqlserver/README.md` |

## 10. Configuración y operación

- **Todo por variables de entorno** (`.env` no versionado; `.env.example` sin valores reales). Sin credenciales por defecto en el código.
- **Configuración de cada módulo leída al usarse:** si falta una variable, el hub arranca y la pantalla dice cuál falta.
- **Dependencias por módulo** (`requirements-<modulo>.txt`) con import diferido.
- **Recarga automática** en desarrollo al cambiar el `.env` (`.flaskenv`).
- **Modo simulación** en los módulos con efectos hacia terceros (Corte de caja) para probar contra el sistema real sin afectarlo.
- **Catálogo:** habilitar o deshabilitar un módulo sin borrar permisos y sin tocar el Programador de tareas.

## 11. Documentación como parte del producto

| Documento | Para |
|---|---|
| `README.md` | Arranque, instalación, comandos y configuración |
| `ARQUITECTURA.md` | Principios, reglas y atomicidad |
| `AGREGAR_MODULO.md` | Paso a paso y lista de verificación para una automatización nueva |
| `INTERFAZ.md` | Plantillas, macros, colores, spinners, confirmaciones y expiración de sesión |
| `LOGS.md`, `EJECUCIONES.md`, `PRUEBAS.md` | Operación y calidad |
| `GLOSARIO.md` | Vocabulario común y actores reales de cada módulo |
| Una guía por módulo | Decisiones, datos de origen, configuración, paso a producción y pendientes |

---

## Límites conocidos (para no sobrevender)

- **Credenciales técnicas con más permisos de los necesarios:** `usrsap` para la base del hub y SAP,
  y `usrSTOD` para el login. Falta pedir a Informática logins de solo lectura.
- **Todos los secretos en un solo `.env`** que lee todo el proceso. Revisarlo cuando haya más módulos con credenciales.
- **Roles fijos en código** (tres). Suficiente hoy; si aparece un rol nuevo (*Auditor*), conviene pasar a permisos declarados por módulo.
- **Retiro de un módulo con tablas** aún no automatizado: se deshabilita en lugar de borrarse.
- **Tareas síncronas, sin cola:** suficiente para los módulos actuales; el punto de conexión está documentado en `EJECUCIONES.md`.
- **Producción:** falta definir el servidor, HTTPS y la cuenta de servicio del Programador de tareas.
