# Arquitectura de ORBIT Canella

ORBIT Canella es un **monolito modular**: una sola aplicación Flask y un solo despliegue,
dividida por dentro en un núcleo común y módulos independientes, uno por automatización contable.

```text
create_app (app/__init__.py)        ← raíz de composición: conecta núcleo, integraciones y módulos
├── app/core/                       ← núcleo: login, permisos, catálogo, ejecuciones, logs
├── app/integraciones/              ← implementaciones de sistemas externos (hoy: STOD)
└── app/modulos/<id>/               ← una carpeta por automatización (plugin)

Dirección de las dependencias:   modulos ──► core ◄── integraciones
                                  (core no importa a ninguno de los dos)
```

Este documento fija las reglas que mantienen esa separación. Las que se pueden verificar
automáticamente están en `tests/test_arquitectura.py` y fallan en `python -m pytest` si se rompen.

---

## Principios

### 1. Módulos tímidos: encapsulación e interfaz pública reducida

Cada módulo oculta cómo está hecho y expone solo un contrato pequeño.

| En el hub | Cómo se cumple |
|---|---|
| Contrato de un módulo | `MODULO = DefinicionModulo(...)` en su `__init__.py`: id, Blueprint, tareas. Nada más es público |
| Contrato del núcleo hacia los módulos | `ejecucion`, `ejecutar_tarea`, `ultimas_ejecuciones`, `ContextoEjecucion`, `ResumenEjecucion`, `get_logger`, `DefinicionModulo`, `es_administrador`, `solo_administradores` |
| Ley de Demeter | Un módulo habla con el núcleo, no recorre objetos del núcleo (`usuario.permisos[0].modulo...`) |

**Verificado:** un módulo no importa otro módulo ni `app.core.models`.

### 2. Inversión de dependencias (DIP)

El código depende de contratos, no de implementaciones concretas.

- El núcleo define el contrato de identidad en `app/core/identidad.py` (`ProveedorIdentidad`,
  `Identidad`, `IdentidadNoDisponible`). STOD lo implementa en `app/integraciones/stod.py`, y
  `create_app` lo registra. En pruebas se registra `ProveedorSimulado` sin tocar el núcleo.
- El núcleo no conoce dónde viven los módulos: `create_app` le indica el paquete
  (`cargar_modulos(app, paquete="app.modulos")`).
- Cuando haya un servicio compartido nuevo (por ejemplo, correo), se hace igual: contrato en
  `core`, implementación en `integraciones`, conexión en `create_app`.

**Verificado:** `app/core` no importa `app/integraciones` ni `app/modulos`.

### 3. Dependencias acíclicas (ADP)

El grafo de imports entre archivos de `app/` no tiene ciclos, **tampoco dentro de funciones**.
Un `import` escondido dentro de una función para esquivar un ciclo es una señal de alarma, no una
solución.

Un ciclo se rompe de dos maneras:

- Extrayendo lo compartido a un archivo del que dependan los dos (así nació `core/peticiones.py`
  entre `auth` y `autorizacion`).
- Invirtiendo la dependencia con un contrato (así nació `core/identidad.py` entre `core` y
  `integraciones`).

**Verificado:** detección de ciclos sobre todos los imports de `app/`.

### 4. Aislamiento de persistencia y DTOs

- Cada módulo tiene sus tablas con prefijo `<ID_MODULO>_` y no modifica las del núcleo (`HUB_`).
- Entre límites se intercambian DTOs inmutables (`ResumenEjecucion`, `Identidad`) o tipos
  simples (`usuario_id: int`), nunca filas ORM ni `current_user`.
- Para relacionar sus registros con el hub, un módulo guarda `ejecucion_id` o `usuario_id`.

### 5. Cuidado con la duplicación accidental

No se unifica código de dos módulos solo porque se parezca. Se extrae a `core` o a
`integraciones` únicamente cuando las dos partes cambian **por el mismo motivo de negocio y al
mismo ritmo**. Ante la duda, se duplica; unificar después es más barato que separar.

> Caso aplicado (28/09/2026): Corte de caja lee su buzón por EWS y Contraseñas por Graph. Por eso
> el contrato `Buzon` y su adaptador viven dentro de `app/modulos/corte_caja/buzon.py`, no en
> `integraciones/`. Cuando TI decida una sola plataforma, el contrato sube a `core` y el
> adaptador a `integraciones` (principio 2).

### 6. Comunicación indirecta entre módulos (eventos en memoria)

**Aún no se implementa.** Hoy ningún módulo necesita avisarle a otro. Cuando aparezca el primer
caso (por ejemplo, "corte cerrado → notificar a otro módulo"):

1. El núcleo declara el evento con las *signals* de Flask (blinker, ya instalado):
   `eventos = Namespace(); corte_cerrado = eventos.signal("corte_cerrado")`.
2. El módulo origen emite `corte_cerrado.send(ejecucion_id=..., datos=<DTO>)` sin saber quién
   escucha.
3. Cada módulo interesado se suscribe en su `__init__.py` y reacciona por su cuenta.

Los eventos llevan DTOs o tipos simples (principio 4) y viven en `core`, nunca en un módulo.

---

## Atomicidad

La atomicidad se revisó en dos sentidos: **transaccional** (una operación se aplica completa o no
se aplica) y **de diseño** (un módulo se agrega o se quita como una unidad).

### Transaccional

| Operación | Estado | Detalle |
|---|---|---|
| Inicio de sesión y bloqueo por intentos | ✅ | Un solo `commit` por intento; el log se escribe después |
| Alta y edición de usuarios y permisos | ✅ | Usuario, rol, estado y permisos en un solo `commit` |
| Sincronización del catálogo | ✅ | Un solo `commit`; si otro proceso sincroniza al mismo tiempo, rollback limpio |
| Ejecución de una tarea | ✅ con reglas | La fila `en_curso` se confirma al iniciar (visibilidad). Lo que la tarea escribe se confirma **junto** con el estado final, o se revierte si falla (prueba `test_ejecucion_fallida_revierte_los_cambios_de_la_tarea`) |
| Efectos fuera de la base (correo, archivos, SAP, STOD) | ⚠️ No transaccionales | Un rollback no los deshace. Ver reglas |
| Ejecución interrumpida (servidor reiniciado o proceso terminado) | ✅ | Al arrancar se marcan `interrumpida` las que siguen `en_curso` tras `EJECUCIONES_INTERRUMPIDAS_HORAS`; también `flask tareas interrumpidas`. Ver [EJECUCIONES.md](EJECUCIONES.md#ejecuciones-interrumpidas) |
| Dos corridas simultáneas del mismo módulo | ✅ | Mutex por módulo garantizado por la base (índice único filtrado). Ver [EJECUCIONES.md](EJECUCIONES.md#ejecución-exclusiva-por-módulo) |

**Reglas para las tareas de un módulo:**

1. **No llamar a `db.session.commit()` dentro de una tarea.** Lo hace `ejecucion()` al terminar.
   Un `commit` intermedio rompe la reversión si la tarea falla después.
2. **No dejar cambios sin confirmar antes de iniciar una ejecución.** El registro inicial los
   confirmaría como efecto secundario.
3. **Efectos externos al final e idempotentes:** primero calcular y validar, después enviar el
   correo, mover el archivo o escribir en SAP. Si la tarea puede repetirse, que no duplique el
   efecto (por ejemplo, verificar si el correo ya se respondió o el archivo ya existe).
4. **Registrar en `ctx.resultado` qué efectos externos se aplicaron**, para saber qué revisar si
   la tarea falla a mitad de camino.
5. **Tareas por lotes: aislar cada elemento.** Si una tarea procesa varios elementos (correos,
   archivos, partidas), atrapa el error de cada uno, lo registra (fila con estado `error`) y sigue
   con los demás, marcando `ctx.estado = "advertencia"`. Las filas de cada elemento se agregan a la
   sesión **después** de sus efectos externos, así un error a mitad de un elemento no deja filas
   suyas a medias. Sin esto, un fallo en el elemento 30 revertiría las filas de los 29 anteriores
   cuyos efectos ya ocurrieron. Referencia: `_Procesador` en `app/modulos/corte_caja/servicios.py`.
6. **Corridas sin nada que hacer:** `ctx.estado = "sin_cambios"` (ver
   [EJECUCIONES.md](EJECUCIONES.md#corridas-sin-cambios)).

### De diseño (módulo como unidad)

| Aspecto | Estado | Detalle |
|---|---|---|
| Agregar un módulo | ✅ | Una carpeta. Descubrimiento, rutas, protección, catálogo, plantillas y logs sin tocar el núcleo |
| Aislamiento de fallos al cargar | ✅ | Un módulo que falla al importarse se registra en logs y el hub sigue funcionando |
| Configuración | ✅ | Variables `<MODULO>_*` en `.env`, leídas por el propio módulo |
| Deshabilitar un módulo | ✅ | Desde el catálogo: bloquea sus rutas sin borrar permisos y **detiene sus tareas**: `ejecutar_tarea` las rechaza sin registrar nada (`ModuloDeshabilitado`, salida 4 en consola). Resuelto el 28/09/2026 |
| Quitar un módulo **sin** tablas | ✅ | Borrar la carpeta; el catálogo lo marca "sin código" |
| Quitar un módulo **con** tablas | ✅ | Las migraciones son una sola cadena de Alembic. El filtro `app/core/migraciones.py` (`include_object`) hace que autogenerate ignore las tablas que no están en los modelos cargados: nunca propone borrarlas. El retiro a propósito es una migración escrita a mano ([AGREGAR_MODULO.md](AGREGAR_MODULO.md#retirar-un-módulo-con-tablas)). Resuelto el 23/11/2026 |
| Dependencias de Python | ⚠️ Parcial | Convención `requirements-<modulo>.txt` en uso desde `corte_caja` (`exchangelib`), con import diferido para que el hub y las pruebas carguen el módulo sin ella. Falta que el catálogo avise cuando un módulo no tiene sus dependencias instaladas |

### Pendientes de atomicidad, en orden

1. ~~**Ejecuciones huérfanas**~~: resuelto el 2026-09-25 (estado `interrumpida`).
2. ~~**Ejecución exclusiva**~~: resuelto el 2026-09-25 (mutex por módulo con índice único filtrado).
3. ~~**Retiro de módulos con tablas**~~: resuelto el 2026-11-23 (filtro `include_object` +
   procedimiento en AGREGAR_MODULO.md).
4. **Dependencias por módulo**: convención adoptada el 28/09/2026 (`requirements-<modulo>.txt`); falta el aviso en el catálogo.

---

## Auditoría de arquitectura (29/09/2026)

Auditoría de los 5 ejes habituales (límites de dominio, backend Flask, persistencia, interfaz,
seguridad/logs). Nada en crítica ni alta. Corregido:

- **N+1 en el listado de aseguradoras**: la plantilla lee `codigos` y `documentos` de cada fila;
  sin `selectinload` eso dispara consultas por fila. Ahora son fijas (no crecen con la cantidad de
  aseguradoras), verificado con una prueba que cuenta las consultas SQL (`tests/conftest.py:
  contar_consultas`, reutilizable para detectar el mismo problema en otro listado).
- **Pool de conexiones a SQL Server sin ajustar**: sin `pool_pre_ping`, una conexión que el
  servidor ya cerró (firewall, VPN, reinicio) fallaba la primera petición en vez de renovarse
  sola. Ahora `pool_pre_ping=True` y `pool_recycle` configurable (`DB_POOL_RECYCLE_SEGUNDOS`,
  280 s por defecto) en `app/config.py`.

Quedó registrado y sin acción, por ser una decisión explícita y no un defecto: el núcleo depende
de Flask y SQLAlchemy directamente (no hay una capa de dominio aislada del framework). Este
documento nunca prometió Clean Architecture/Hexagonal; su principio 4 exige DTOs **entre módulo y
núcleo**, no dentro de un módulo hacia su propia plantilla. Para un monolito interno de este
tamaño, esa capa extra sería costo sin beneficio.

**Pendiente de esta auditoría:** revisión de comentarios (el porqué, no el cómo) →
[PLAN_COMENTARIOS.md](PLAN_COMENTARIOS.md).

---

## Auditoría de independencia técnica: `expedientes_seguros` (07/10/2026)

Pedido específico: revisar la salud del módulo como pieza del hub — acople y desacople, no las
5 fases generales (esas ya se hicieron el 29/09). Evidencia, no opinión:

| Eje (principio) | Verificación | Resultado |
|---|---|---|
| Módulo tímido (1) | `tests/test_arquitectura.py` + lectura manual de los 8 archivos | Solo importa `app.core.logs`, `app.core.permisos`, `app.core.paginacion`, `app.core.registro` y `app.extensions.db` — nunca `app.core.models` ni otro módulo. Contrato público: un `MODULO = DefinicionModulo(...)` en `__init__.py`, nada más |
| Acople inverso (¿el hub depende del módulo?) | `grep -rl "expedientes_seguros" app/core app/integraciones app/modulos/{corte_caja,ejemplo}` | Vacío: nada fuera del módulo lo importa |
| DIP (2) | Lectura de `sap.py`/`servicios.py` | `RepositorioSap` (Protocol) es el único contrato con SAP; `SapSql` lo implementa y `crear_repositorio()` es la única costura. Las pruebas usan `SapFalso` sin tocar pyodbc |
| Ciclos (3) | `tests/test_arquitectura.py::test_sin_ciclos_de_importacion` | Pasa |
| Aislamiento de persistencia (4) | `grep __tablename__` | Las 5 tablas usan el prefijo `EXPEDIENTES_SEGUROS_*`; ninguna toca `HUB_*` |
| DTO en el límite (4) | `grep current_user` | Un solo punto (`views.py`): cruza a `servicios.armar_paquete` como `usuario_id: int`, nunca como objeto |
| Dependencias opcionales | `grep` de imports a nivel de módulo | `pypdf`, `pypdfium2` y `pyodbc` están diferidos dentro de función (`documentos.py`, `sap.py`); el hub carga el módulo sin esas librerías instaladas, igual que `corte_caja` con `exchangelib` |
| Config propia | Lectura de `configuracion.py` | Solo variables `EXPEDIENTES_*`, leídas al usarse (no al importar), sin tocar `app/config.py` |
| Código muerto / higiene | `pyflakes app/modulos/expedientes_seguros/*.py` | Limpio (los 2 avisos son los `# noqa: F401` ya documentados de `aseguradoras`/`models`, imports por efecto secundario) |

**Nada en crítica ni alta.** Un hallazgo real de atomicidad, corregido:

- **Carpeta huérfana si fallaba un archivo "aparte" a medio armar** (`servicios.armar_paquete`):
  el `try/except` solo envolvía el `commit`, no la escritura de archivos. Si fallaba escribir un
  PDF "aparte" (disco lleno, permisos) después de escribir el principal, quedaba una carpeta con
  archivos sueltos **sin fila de `Paquete`** — y `purgar_antiguos()` solo recorre filas de
  `Paquete`, así que esa carpeta (con datos personales: DPI, tarjeta de circulación) nunca se
  habría borrado. Corregido ampliando el `try` a todo el armado de archivos; probado forzando el
  fallo (`test_si_falla_un_archivo_aparte_no_queda_nada_a_medias`): no queda carpeta ni fila.

Quedó registrado y sin acción, por ser un costo aceptado y no un defecto: las cachés en memoria de
`servicios.py` (`_anexos`, `_originales`) no tienen el mismo candado entre sí (`_originales` sí,
`_anexos` no) — en CPython una asignación de diccionario es atómica, así que el peor caso es una
consulta de más a SAP, no corrupción. Si el módulo pasara a varios workers con caché compartida,
revisar primero.

---

## Auditoría del monolito modular antes de versionar en GitHub (23/11/2026)

Pedido: validar que la arquitectura aguanta que se sigan agregando módulos, antes de crear el
repositorio. Se revisó el código traído de la copia de trabajo del escritorio (envío SMTP de
`expedientes_seguros`, migración `5e2b9c4d7a10`).

| Eje | Verificación | Resultado |
|---|---|---|
| Dirección de dependencias, módulos tímidos, ciclos (1, 2, 3) | `tests/test_arquitectura.py` + `grep` de imports `app.*` en `app/modulos` | ✅ Los módulos solo usan `registro`, `logs`, `ejecuciones`, `permisos`, `paginacion` y `db` |
| Persistencia (4) | `grep __tablename__`, `ForeignKey` | ✅ 13 tablas, todas con el prefijo de su dueño; ninguna llave foránea de un módulo hacia `HUB_*` |
| Plantillas y estáticos | Estructura de carpetas | ✅ `templates/<id>/`; estáticos del módulo en `/m/<id>/static` |
| Configuración | `grep` en `app/config.py` | ✅ Ninguna variable de módulo en el núcleo |
| Envío SMTP nuevo (DIP, atomicidad) | Lectura de `envio.py`, `servicios.enviar` | ✅ Contrato `Enviador` (simulable); marca con `UPDATE` condicional antes de enviar y desmarca si falla: un doble clic no duplica el correo |

**Corregido (alta):**

- **Migraciones que podían borrar tablas de otro módulo.** Con una sola cadena de Alembic,
  generar una migración con `AUTOMATE_MODULOS` limitado (o con un módulo que no cargó) proponía
  `DROP TABLE` de las tablas no cargadas. Ahora `app/core/migraciones.py` las ignora
  (`tests/test_migraciones.py` prueba que sin el filtro el riesgo existe y con él no).
- **Reglas que se cumplían solo por revisión manual.** Se agregaron a `tests/test_arquitectura.py`:
  prefijo de tablas por dueño (`HUB_` en el núcleo, `<ID_MODULO>_` en cada módulo), ningún módulo
  nombra tablas `HUB_*`, y las plantillas de cada módulo viven en `templates/<id>/` (Flask junta
  todas las carpetas de plantillas: dos `inicio.html` sueltos se pisarían).

**Registrado, sin acción por ahora:**

- **Correo (principio 5):** `corte_caja` lee por EWS y `expedientes_seguros` envía por SMTP. Al
  llegar el tercer módulo que **envíe** correo, `Enviador` sube a `core` y `EnviadorSmtp` a
  `integraciones/` (principio 2), en lugar de copiar `envio.py`.
- **Un solo `.env`** con las credenciales de todos los módulos (ya en PLAN_DE_TRABAJO).
- **Permisos dentro de un módulo:** quien entra a Expedientes ve todos los paquetes. Por confirmar
  si es la regla de negocio.
- `DESTINO_PRUEBA` (`servicios.py`) queda en el código a propósito: es la red de seguridad del modo
  prueba (si no hay destino guardado, el correo nunca sale hacia Cobros); un administrador lo
  cambia desde la pantalla, sin tocar código.

**Antes de subir a GitHub:** `.gitignore` ahora excluye `.coverage`, `htmlcov/`, `.venv.old/` y
`.claude/settings.local.json`. No hay contraseñas en archivos versionados (todas vienen del
`.env`); `instance/`, `contexto/` y `logs/` (datos personales) ya estaban fuera. Los documentos
tienen IPs y correos internos: el repositorio debe ser **privado**.

---

## Auditoría pragmática del hub (23/11/2026)

Alcance: solo la plataforma (login, sesión, autorización, roles, catálogo, ejecuciones, logs,
consola, configuración, cabeceras, interfaz base), no los módulos. Sin errores de lógica; los
hallazgos están en la publicación y en límites que conviene fijar antes de sumar módulos.

| # | Hallazgo | Estado |
|---|---|---|
| N1 | Waitress solo habla HTTP: si el hub se publica en la red sin proxy con certificado, las contraseñas de STOD viajan sin cifrar | **Pendiente de decisión**: proxy con HTTPS (IIS/Nginx); mientras, no publicar el puerto fuera del servidor |
| N2 | Sin tope de tamaño de las peticiones: cada módulo tenía que acordarse de poner el suyo | **Corregido**: `SUBIDA_MAXIMA_MB` (25) → `MAX_CONTENT_LENGTH`; 413 «Archivo demasiado grande» en español (HTML y JSON). Pruebas en `tests/test_acceso.py` |
| N3 | Detrás de un proxy, el bloqueo de login por IP se vuelve global (todos comparten la IP del proxy) | Pendiente: activar `ProxyFix` al resolver N1 |
| N4 | El historial de quién dio o quitó accesos solo vive en los logs (se borran a los 90/180 días) | Pendiente de decisión: tabla de auditoría permanente |
| N5 | Escala: la búsqueda de logs lee archivos completos; las tareas lanzadas desde un botón ocupan un hilo de Waitress; `/salud` no prueba la base | Registrado, sin acción |

---

## Cuándo revisar este documento

- Antes de agregar un módulo o un servicio compartido nuevo.
- Si `tests/test_arquitectura.py` falla: se corrige el diseño, no la prueba. Si de verdad hay
  que cambiar una regla, se cambia aquí primero y se explica por qué.
- Al cerrar cualquiera de los pendientes de atomicidad: actualizar su fila.
