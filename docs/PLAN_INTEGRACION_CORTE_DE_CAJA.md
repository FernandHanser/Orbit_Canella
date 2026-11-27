# Módulo Corte de caja diario (`corte_caja`)

Estado al 27/11/2026: **funcionalidad del prototipo actualizada (reglas y tablero) y sin modo
simulación.** Falta el corte: apagar el prototipo y programar la tarea (ver [Paso a producción](#paso-a-producción)).

| Paso | Estado |
|---|---|
| Migración `b5d844416447` (tablas + 6 empresas) en 128.1.200.70 | ✅ 28/09/2026 |
| `exchangelib` en el `.venv` de desarrollo | ✅ 28/09/2026 |
| Variables `CORTE_CAJA_*` en `.env` (trasladadas del `.env` de producción del prototipo) | ✅ 28/09/2026 |
| Conexión al buzón por EWS (a través del proxy corporativo) | ✅ 28/09/2026: primera lectura, 1 procesado y 1 rechazado (fecha futura), ambos correctos |
| Actualización con lo que el prototipo agregó hasta `9f62359` (26/11/2026) | ✅ 27/11/2026 en `feature/cortes` ([detalle](#actualización-del-27112026)) |
| Migración `5869c708f797` (estructura oficial de carpetas) en 128.1.200.70 | ✅ 27/11/2026 |
| Tablero del prototipo (Procesadas, Rechazadas, Cuadre mensual, Directorio de tiendas) y retiro del modo simulación | ✅ 27/11/2026 en `feature/cortes` ([detalle](#tablero-y-configuración-27112026)) |
| Migración `abe14a897c2b` (directorio de cajas) y carga del directorio en 128.1.200.70 | ⏳ |
| Corte: apagar el prototipo y programar la tarea | ⏳ |

Migrado desde `RicardoCruzLemus/AUTOMATIZACION_CORTE_DE_CAJA_DIARIO`, rama `dev` (commit
`eb1d8ea`, 21/09/2026) y actualizado hasta `9f62359` (26/11/2026). Copia de referencia local:
`GitHub/AUTOMATIZACION_CORTE_DE_CAJA_DIARIO_REF`.

---

## Actualización del 27/11/2026

Entre `eb1d8ea` y `9f62359` el prototipo siguió cambiando en producción. Se trasladó solo lo que
cambia el comportamiento con las agencias o dónde quedan los archivos:

| # | Cambio del prototipo (commit) | En el hub |
|---|---|---|
| A1 | **Estructura oficial de carpetas** (`083118e`): `Vesa\1.Año 2026\202611NOVIEMBRE\27-11-26`; Canella sin espacio en `1.Año2026`; Mauto con `11 NOVIEMBRE 2026` | Columna `plantilla_carpeta` en `CORTE_CAJA_EMPRESAS`, editable por consola (`empresa-modificar --plantilla`). La migración `5869c708f797` fija las tres estructuras y los nombres oficiales: MAQUIPOS → Maquipos, VESA → Vesa, MR. Credit → **Mister Credit**, CANELLA → Canella |
| A2 | **Fecha de los archivos igual a la del asunto** (`6f41755`) | Rechazo «Error en fechas» si un archivo que empieza con `DDMMAAAA` trae otra fecha. Los que no empiezan con fecha no se comparan |
| A3 | **Adjuntos auxiliares** (`2fc7d40`): `Anulacion.pdf`, `Boleta.pdf` | Se archivan junto al corte si al menos un archivo tiene el formato `FECHA-EMPRESA-DOCUMENTO`. Solo auxiliares → rechazo |
| A4 | **Fecha rescatada del archivo** (`c9f840a`): asunto sin fecha o con año equivocado | Si la fecha del asunto falta o no es válida, se usa la del primer PDF o Excel que empiece con una fecha válida (mismas reglas: existe, no futura, gracia de 45 días) |
| A5 | **«Sin movimiento»** (`3596b4d`): la caja avisa que no tuvo movimiento y no adjunta nada | Estado nuevo `sin_movimiento`, pestaña **Sin movimiento** y subcarpeta del buzón del mismo nombre. No se responde. Se guardan empresa y fecha si el asunto las trae |

**A5 corrige un defecto del prototipo.** Su detector aceptaba frases como «en 0» (que coincide
con cualquier fecha: «corte en 05/10») o «no» a 35 caracteres de «ventas» («no olvidar revisar las
ventas»). Un correo al que **solo le faltaban los adjuntos** quedaba como «sin movimiento»: no se
avisaba a la caja y el corte faltante no se veía. En el hub la negación tiene que ir junto a la
palabra de actividad (a lo sumo cuatro palabras de relleno de una lista cerrada), se evalúan solo
el asunto y los primeros 500 caracteres del cuerpo (sin firmas ni respuestas citadas) y se
quitaron «en 0», «n/a» y «no aplica». Ante la duda se rechaza: el rechazo le pide a la caja que
reenvíe, el falso «sin movimiento» lo esconde.

**No se trasladó:**

- Reintentos y marca de agua (`9f62359`): el hub ya los resuelve con el buzón como cola (C1).
- `reply()` en lugar de `reply_all()` (`6628295`): el hub ya respondía solo al autor (C2).
- Etiqueta `CORREGIDO` en el log, año 2025 fijo en el código, modo oscuro, refresco cada 5
  segundos y demás cambios visuales del panel del prototipo, y los `scripts/patch_*.py`: no cambian
  el resultado. El tablero se trasladó en la [sección siguiente](#tablero-y-configuración-27112026).

## Tablero y configuración (27/11/2026)

Se trasladó la **funcionalidad** del tablero del prototipo (`index.html`, `tiendas_api.py`) con la
plantilla del hub: el menú lateral del prototipo es una fila de pestañas.

| Prototipo | En el hub |
|---|---|
| Tarjetas Aceptadas, Rechazadas, Tiendas registradas | Las mismas tres, arriba del tablero |
| Procesadas: fecha, archivo, estado, correo, asunto; buscar por archivo, correo o asunto y por fechas | Pestaña **Procesadas** (correos guardados y con error), con filtros y paginación del hub |
| Rechazadas: caja, remitente, asunto, motivo, adjuntos; buscar por caja, remitente o asunto | Pestaña **Rechazadas**. Los adjuntos de cada correo se guardan ahora en `CORTE_CAJA_CORREOS.adjuntos` |
| Cuadre mensual: mes, calendario por día, estado de cada caja, tarjetas recibidos / sin movimiento / faltantes | Pestaña **Cuadre mensual** (`cuadre.py`): mismos colores del calendario y mismas reglas para reconocer la caja |
| Directorio de cajas y tiendas (`cajas.db`) | **Configuración → Directorio de tiendas** (`CORTE_CAJA_CAJAS`): alta, edición, baja y búsqueda para los usuarios del módulo, como en el prototipo. Carga inicial: `flask --app wsgi corte_caja cajas-importar <ruta de cajas.db>` |

**Se quitó:** la pantalla de Empresas (las empresas se siguen usando para decidir la carpeta; se
administran por consola), el botón «Revisar buzón ahora» (revisa la tarea programada) y el modo
simulación. `CORTE_CAJA_MODO` ya no se lee; las filas que dejó la simulación se conservan en la
base con `simulado = 1`, pero el tablero no las muestra.

**Corrección en el cuadre.** El prototipo comparaba el remitente con cada palabra del campo
correo de la caja; «CREDITOS COBRADORES» tiene «se turnan los cobradores», así que cualquier
remitente con «se» en su dirección contaba como corte de los cobradores. Aquí solo cuentan las
direcciones con `@`, completas. Si un mismo día una caja manda un corte y un «sin movimiento», gana
el corte.

---

## Qué hace

Recibe por correo los cortes de caja de las agencias, valida asunto y adjuntos, guarda los
archivos en la carpeta de la empresa con su estructura oficial (`Vesa\1.Año 2026\202611NOVIEMBRE\27-11-26`)
y, si algo no cumple, responde al remitente explicando qué corregir.

```text
Programador de tareas (cada 5 min)
  └─ flask tareas ejecutar corte_caja procesar
       └─ por cada correo de la bandeja de entrada (lote de 20, del más antiguo al más reciente):
            automático o remitente externo ─► Ignorados       (no se responde)
            avisa «sin movimiento» y sin PDF/Excel ─► Sin movimiento (no se responde)
            asunto o adjuntos inválidos     ─► responder rechazo ─► Rechazados
            válido                          ─► guardar adjuntos  ─► Procesados
            falla inesperada                ─► Error              (la corrida sigue)
```

## Decisiones (28/09/2026)

| Decisión | Motivo |
|---|---|
| **El buzón es la cola**: cada correo se mueve a una subcarpeta al terminar; lo que está en la bandeja de entrada está pendiente | La marca de agua del prototipo avanzaba aunque un correo fallara, y ese corte se perdía en silencio |
| **Se elimina la carpeta local** (`SOURCE_DIR` + `watchdog`) | Ya no se usa. Además aplicaba reglas distintas a las del correo |
| **Solo remitentes de `@canella.com.gt`** (configurable) y **respuesta solo al remitente** | El prototipo respondía con `reply_all` a cualquiera, con el asunto sin escapar: un externo podía enviar HTML a terceros desde el buzón corporativo |
| **Ruido de ejecuciones resuelto en el núcleo** antes del módulo | 288 corridas diarias sin nada que hacer. Ver estado `sin_cambios` en [EJECUCIONES.md](EJECUCIONES.md#corridas-sin-cambios) |
| **Cliente de correo dentro del módulo**, no en `integraciones/` | Principio 5 de [ARQUITECTURA.md](ARQUITECTURA.md): Contraseñas usa Graph; se unifica cuando TI decida una sola plataforma |

## Defectos del prototipo corregidos

| # | Defecto | Corrección |
|---|---|---|
| C1 | Si fallaba la red o la escritura, el correo no se marcaba, pero la marca de agua avanzaba: **el corte se perdía** | El buzón es la cola; mover es el último paso |
| C2 | Asunto y nombres de adjuntos sin escapar en el HTML del rechazo, enviado con `reply_all` | Plantilla Jinja con autoescape; `reply` solo al autor |
| C3 | Rechazaba cualquier correo: boletines, respuestas automáticas, rebotes | Se ignoran los automáticos (`Auto-Submitted`, `X-Auto-Response-Suppress`, `Precedence`, `mailer-daemon`…) y los externos |
| C4 | Aceptaba fechas inexistentes (`31/02/2026`) y días futuros (solo revisaba el año) | La fecha debe existir y no ser posterior a hoy |
| C5 | Empresa por defecto `CANELLA`: lo no reconocido se archivaba ahí | Si ninguna empresa coincide, se rechaza. **Cambio de comportamiento**: confirmarlo en la corrida en paralelo |
| C6 | La carpeta local aceptaba otras extensiones y no validaba nada | Eliminada |
| C7 | `net use` con contraseña en la línea de comandos, usuario fijo en el código, código muerto (`smtp_service.py`, `test_imap.py`, `check_emails.py`) | La cuenta de servicio tiene permiso sobre la carpeta; todo por `.env`; no se migró el código muerto |

Se conservan las reglas afinadas en producción: palabras clave tolerantes a errores de
escritura, periodo de gracia de 45 días para el año anterior, dígitos pegados que no se
confunden con la fecha (caso `MORIO2`), imágenes de firmas ignoradas, formato de nombre
`FECHA-EMPRESA-DOCUMENTO` y el texto del correo de rechazo.

---

## Estructura

```text
app/modulos/corte_caja/
├── __init__.py        MODULO: id "corte_caja", tarea "procesar"
├── reglas.py          reglas puras: fecha, empresa, palabras clave, adjuntos, remitente, nombre seguro
├── buzon.py           contrato Buzon + BuzonEws (exchangelib)
├── archivador.py      escritura idempotente (SHA-256) en la carpeta compartida
├── servicios.py       tarea procesar: orquesta y aísla cada correo
├── configuracion.py   variables CORTE_CAJA_* (leídas al ejecutar, no al importar)
├── models.py          CORTE_CAJA_EMPRESAS, _CORREOS, _ARCHIVOS, _CAJAS
├── views.py           tablero: pestañas Procesadas, Rechazadas y Cuadre mensual; detalle
├── cuadre.py          reglas puras del cuadre mensual: a qué caja pertenece un correo, colores del calendario
├── directorio.py      configuración: directorio de cajas y tiendas (usuarios del módulo)
├── cli.py             flask corte_caja empresas | empresa-agregar | empresa-modificar | cajas-importar
└── templates/corte_caja/   inicio, detalle, cajas, caja_form y correo_rechazo.html
```

Dependencias: solo el núcleo (`ejecuciones`, `logs`, `paginacion`, `registro`) y `app.extensions`.
`tests/test_arquitectura.py` lo verifica.

## Atomicidad

- **Sin `commit` en la tarea.** Las filas se confirman con el estado final de la ejecución.
- **Aislamiento por correo.** Un correo que falla queda en `Error` con su motivo y la corrida sigue;
  la ejecución termina en `advertencia`. La reversión total queda solo para caídas del proceso.
- **Orden de efectos:** clasificar → guardar archivos o responder → **mover el correo (último)** →
  registrar la fila.
- **Si la corrida se corta** antes de mover, el correo sigue en la bandeja y se reprocesa. El
  archivador reconoce el archivo por su SHA-256 y no lo duplica (queda marcado "Ya existía"). En el
  peor caso se repite un correo de rechazo; nunca se pierde un corte.
- Un archivo distinto con el mismo nombre (una corrección) se guarda como `nombre (1).pdf`.

## Tablas

| Tabla | Reemplaza a | Contenido |
|---|---|---|
| `CORTE_CAJA_EMPRESAS` | Lista fija en `extract_company` y rutas fijas por empresa | Carpeta, palabras clave (coma), orden, activa y `plantilla_carpeta` (subcarpetas por fecha). Las migraciones siembran las 6 del prototipo con sus nombres y estructuras oficiales |
| `CORTE_CAJA_CORREOS` | `correos_procesados.json`, `rejected_logs.json` | message_id, asunto, remitente, recibido, estado (`procesado`, `sin_movimiento`, `rechazado`, `ignorado`, `error`), motivo, empresa, fecha del corte, adjuntos (nombres, uno por línea), ejecucion_id. `simulado` queda solo para las filas del modo simulación retirado |
| `CORTE_CAJA_ARCHIVOS` | `transfer_logs.json` | Nombre original y final, carpeta relativa, SHA-256, tamaño, duplicado |
| `CORTE_CAJA_CAJAS` | `cajas_directorio` de `cajas.db` | Categoría, nombre de la caja, responsable, correo(s). Sin datos en el repositorio: se carga con `cajas-importar` |

Sin recorte a 30 días: la historia queda completa. `message_id` no es único: un correo que se
devuelve a la bandeja para reintentarlo genera otra fila.

## Configuración

### Traslado desde el prototipo (28/09/2026)

Valores tomados del `.env` de producción del prototipo (el de la copia local
`GitHub/AUTOMATIZACION_CORTE_DE_CAJA_DIARIO` es de una versión anterior con Gmail y un destino
distinto: no usarlo).

| Prototipo | Hub | Nota |
|---|---|---|
| `DEST_DIR=\\128.1.200.171\Cortes-de-caja$\` | `CORTE_CAJA_DESTINO=\\128.1.200.171\Cortes-de-caja$` | Recurso oculto (`$`), sin la barra final |
| `EXCHANGE_EMAIL` | `CORTE_CAJA_BUZON=automatizacionescaja@canella.com.gt` | Igual |
| usuario fijo en `get_exchange_account()` | `CORTE_CAJA_EWS_USUARIO=automatizacionescaja` | Igual |
| `EXCHANGE_SERVER` | `CORTE_CAJA_EWS_SERVIDOR=owa.canella.com.gt` | Igual |
| `EXCHANGE_PASSWORD` | `CORTE_CAJA_EWS_CONTRASENA='…'` | Entre comillas simples: contiene `$` |
| — | `CORTE_CAJA_EWS_PROXY=http://128.1.200.140:8080` | **Nuevo.** Desde la red interna, `owa.canella.com.gt` resuelve a la IP pública (200.6.246.155) y solo responde a través del proxy corporativo, como lo usa el navegador. Sin él: `ConnectTimeoutError` |
| `SERVER_USERNAME`/`SERVER_PASSWORD` (`itcanella`), `IPC_SHARE` | — | No se trasladan: la cuenta que ejecuta la tarea necesita permiso de escritura en la carpeta |
| `BASIC_AUTH_*` | — | No se usan: el panel usa el login del hub |
| `SOURCE_DIR`, `IMAP_*`, `SMTP_*` | — | No se usan |

### Sin modo simulación (desde el 27/11/2026)

La tarea siempre responde, guarda archivos y mueve los correos. El prototipo sigue leyendo **el
mismo buzón**, así que **no hay que programar la tarea del hub en ningún servidor mientras el
prototipo esté encendido**:

- el hub movería los correos a sus subcarpetas y el prototipo dejaría de verlos, o al revés;
- una agencia podría recibir dos correos de rechazo por el mismo envío.

Antes de llevar esta versión a un servidor, revisar en su Programador de tareas que no exista
la tarea `corte-caja-5min` (ver [Paso a producción](#paso-a-producción)). El `.env` se lee al
arrancar: **reiniciar el hub** después de cualquier cambio.

### Variables

En `.env` (plantilla en `.env.example`). Sin valores por defecto para credenciales; si falta
alguna obligatoria, la ejecución termina en error con la lista de las que faltan.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `CORTE_CAJA_DESTINO` | Sí | Raíz de la carpeta compartida (hoy `\\128.1.200.171\Cortes-de-caja$`) |
| `CORTE_CAJA_BUZON` | Sí | Dirección del buzón del robot (también aparece en el rechazo como destino de reenvío) |
| `CORTE_CAJA_EWS_SERVIDOR`, `_EWS_USUARIO`, `_EWS_CONTRASENA` | Sí | Acceso EWS (hoy `owa.canella.com.gt`, usuario `automatizacionescaja`) |
| `CORTE_CAJA_EWS_PROXY` | No | Proxy HTTP para llegar al EWS, p. ej. `http://128.1.200.140:8080`. Solo lo usa exchangelib |
| `CORTE_CAJA_DOMINIOS` | No (`canella.com.gt`) | Dominios de remitente atendidos, separados por coma |
| `CORTE_CAJA_LOTE` | No (20) | Correos por corrida |
| `CORTE_CAJA_RECIBIDOS_DESDE` | No | Fecha y hora UTC `AAAA-MM-DDTHH:MM`: se ignoran los anteriores |

Dependencia: `pip install -r requirements-corte_caja.txt` (`exchangelib`). Solo en el servidor
que ejecuta la tarea; el hub carga el módulo sin ella y las pruebas no la usan.

## Operación

| Qué | Cómo |
|---|---|
| Tarea programada | Programador de tareas cada 5 min: `flask.exe --app wsgi tareas ejecutar corte_caja procesar --proceso corte-caja-5min` ([EJECUCIONES.md](EJECUCIONES.md#sin-sesión-web-tareas-programadas)) |
| Revisar ya | Desde la consola del servidor: `flask --app wsgi tareas ejecutar corte_caja procesar` (el tablero ya no tiene botón) |
| ¿El robot está funcionando? | Revisor: pie de la tarjeta en el inicio ("Última revisión hace 4 min" / "Falló hace…"). Informática: **Administración → Ejecuciones** y **Logs**, con el error técnico y la traza. El tablero del módulo no muestra ejecuciones: serían errores técnicos para un actor que no los resuelve |
| Tablero | Pestañas **Procesadas**, **Rechazadas** y **Cuadre mensual**, con las tarjetas Aceptadas, Rechazadas y Tiendas registradas |
| Directorio de tiendas | **Directorio de tiendas** (configuración): todos los usuarios del módulo agregan, editan y eliminan cajas. Carga inicial: `flask --app wsgi corte_caja cajas-importar <ruta de cajas.db>` (se puede repetir: no duplica) |
| Historial del prototipo | Al apagarlo: `flask --app wsgi corte_caja historial-importar --procesados transfer_logs.json --rechazados rejected_logs.json`. Reagrupa en correos los registros por archivo, pasa la hora de Guatemala a UTC y marca las filas con `ejecucion_id = importado-prototipo`. Sin huella ni tamaño de archivos (el prototipo no los guardaba): los nombres van a `adjuntos`. Se puede repetir sin duplicar y al final sugiere el valor de `CORTE_CAJA_RECIBIDOS_DESDE` |
| Empresas | Sin pantalla: `flask --app wsgi corte_caja empresas`, `empresa-agregar`, `empresa-modificar` (`--claves`, `--orden`, `--activa/--inactiva`, `--plantilla`) |
| Subcarpetas por fecha | Opción `--plantilla` de cada empresa. Fichas: `{AAAA}` año, `{AA}` año en dos dígitos, `{MM}` mes en número, `{MES}` mes en mayúsculas, `{Mes}` mes con inicial mayúscula, `{DD}` día; carpetas separadas por `/`. Debe incluir día, mes y año. Cambiarla afecta solo a los cortes nuevos |
| Reintentar un correo con error | Corregir la causa y moverlo en Outlook de `Error` a la bandeja de entrada |
| Reprocesar con otra fecha de referencia | `--param hoy=AAAA-MM-DD` |

Quién ve el tablero y edita el directorio: quien tenga el módulo asignado en **Usuarios y
permisos**. Las empresas solo cambian por consola (quien tiene acceso al servidor). Todo cambio
queda en el log (`corte_caja.caja_*` y `corte_caja.empresa_*`, con los valores antes y después).

---

## Paso a producción

El prototipo no mueve correos, así que la bandeja de entrada tiene todo el histórico. Por eso el
corte se hace con `CORTE_CAJA_RECIBIDOS_DESDE`.

1. **Base de datos**: `b5d844416447` (28/09/2026) y `5869c708f797` (27/11/2026) aplicadas. Falta
   `abe14a897c2b` (directorio de cajas): `flask --app wsgi db upgrade`. Sin ella, el tablero
   responde **500** (`CORTE_CAJA_CAJAS` inexistente).
2. **Directorio**: `flask --app wsgi corte_caja cajas-importar <ruta del cajas.db del prototipo>` y
   revisar el conteo en **Directorio de tiendas**.
3. **Servidor**: `pip install -r requirements-corte_caja.txt` y variables `CORTE_CAJA_*` en `.env`.
   `CORTE_CAJA_MODO` ya no se usa: se puede borrar. **No programar la tarea todavía.**
4. **Corte**:
   1. Detener el prototipo (y su túnel de cloudflared).
   2. `CORTE_CAJA_RECIBIDOS_DESDE` = fecha y hora UTC del último correo que procesó el prototipo.
   3. Programar la tarea cada 5 min con la cuenta de servicio que tiene permiso de escritura en la carpeta.
   4. Los primeros días, revisar en el tablero: rechazos por **empresa no reconocida** (C5),
      remitentes internos marcados como externos (X.500 no resuelto), que las rutas (detalle →
      Archivos → Carpeta) sean las del prototipo, en especial **Mister Credit** y Mauto, y correos
      sin adjuntos rechazados que el prototipo habría dado por «sin movimiento» (A5).
5. **Retiro**: archivar el repo del prototipo (hacerlo privado; ver Fase 0 en
   [PLAN_DE_TRABAJO.md](PLAN_DE_TRABAJO.md)).

## Pruebas

`tests/test_corte_caja.py` (83 pruebas): reglas con casos reales de asuntos, archivador
(idempotencia y ruta fuera de la raíz), tarea con `BuzonFalso` (archivado, rechazo escapado y
solo al remitente, ignorados, aislamiento de errores, reintento sin duplicar, `RECIBIDOS_DESDE`,
configuración incompleta, reversión ante caída, `CORTE_CAJA_MODO=simulacion` ignorado), las tres
estructuras de carpetas y la validación de plantillas, fecha de los archivos contra la del asunto,
adjuntos auxiliares, fecha rescatada del archivo, «sin movimiento» (incluidos los falsos
positivos del prototipo, que deben rechazarse), tablero (pestañas, tarjetas, sin filas simuladas,
sin botón ni pantalla de empresas), cuadre mensual (reglas puras y por caja en pantalla),
directorio de tiendas y CLI (empresas e importación del directorio).
`tests/test_migraciones.py` verifica los nombres y subcarpetas que deja `5869c708f797` y su reversa.

No cubren: EWS real (resolución de remitentes X.500, creación de subcarpetas, respuesta, el
cuerpo del mensaje con `text_body`) ni la carpeta de red real. Eso se valida los primeros días
después del corte.

## Pendiente con el área usuaria

- Confirmar el rechazo cuando el asunto no nombra la empresa (antes caía en CANELLA).
- Si agencias externas envían desde otros dominios, agregarlos a `CORTE_CAJA_DOMINIOS`.
- Si el correo de confirmación de éxito debe volver a enviarse (en el prototipo estaba deshabilitado; no se migró).
