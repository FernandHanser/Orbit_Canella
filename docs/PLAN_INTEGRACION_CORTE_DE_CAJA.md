# Módulo Corte de caja diario (`corte_caja`)

Estado al 28/09/2026: **implementado, migración aplicada en `AUTOMATE_CANELLA` (128.1.200.70) y
leyendo el buzón real en modo simulación.** Falta la corrida en paralelo y el corte (ver [Paso a producción](#paso-a-producción)).

| Paso | Estado |
|---|---|
| Migración `b5d844416447` (tablas + 6 empresas) en 128.1.200.70 | ✅ 28/09/2026 |
| `exchangelib` en el `.venv` de desarrollo | ✅ 28/09/2026 |
| Variables `CORTE_CAJA_*` en `.env` (trasladadas del `.env` de producción del prototipo) | ✅ 28/09/2026 |
| Conexión al buzón por EWS (a través del proxy corporativo) | ✅ 28/09/2026: primera lectura, 1 procesado y 1 rechazado (fecha futura), ambos correctos |
| Corrida en paralelo en modo simulación | ⏳ |
| Corte a modo real y retiro del prototipo | ⏳ |

Migrado desde `RicardoCruzLemus/AUTOMATIZACION_CORTE_DE_CAJA_DIARIO`, rama `dev` (commit
`eb1d8ea`, 21/09/2026). Copia de referencia local: `GitHub/AUTOMATIZACION_CORTE_DE_CAJA_DIARIO_REF`.

---

## Qué hace

Recibe por correo los cortes de caja de las agencias, valida asunto y adjuntos, guarda los
archivos en `<Empresa>/<Año>/<Mes>/<DD-MM-AAAA>/` de la carpeta compartida y, si algo no cumple,
responde al remitente explicando qué corregir.

```text
Programador de tareas (cada 5 min)
  └─ flask tareas ejecutar corte_caja procesar
       └─ por cada correo de la bandeja de entrada (lote de 20, del más antiguo al más reciente):
            automático o remitente externo ─► Ignorados      (no se responde)
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
├── models.py          CORTE_CAJA_EMPRESAS, _CORREOS, _ARCHIVOS
├── views.py           panel: pestañas por estado, filtros, detalle, "Revisar buzón ahora"
├── empresas.py        CRUD de empresas en el panel (solo administradores del hub)
├── cli.py             flask corte_caja empresas | empresa-agregar | empresa-modificar
└── templates/corte_caja/   inicio, detalle, empresas y correo_rechazo.html
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
| `CORTE_CAJA_EMPRESAS` | Lista fija en `extract_company` | Carpeta, palabras clave (coma), orden, activa. La migración siembra las 6 del prototipo |
| `CORTE_CAJA_CORREOS` | `correos_procesados.json`, `rejected_logs.json` | message_id, asunto, remitente, recibido, estado, motivo, empresa, fecha del corte, simulado, ejecucion_id |
| `CORTE_CAJA_ARCHIVOS` | `transfer_logs.json` | Nombre original y final, carpeta relativa, SHA-256, tamaño, duplicado |

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

### Por qué arranca en modo simulación

El prototipo sigue leyendo **el mismo buzón**. Con los dos en modo real:

- el hub movería los correos a sus subcarpetas y el prototipo dejaría de verlos, o al revés;
- una agencia podría recibir dos correos de rechazo por el mismo envío;
- el hub rechaza casos que el prototipo aceptaba (asunto sin empresa, fecha futura o inexistente),
  y esos rechazos llegarían a las agencias sin haberlos revisado.

En simulación el hub lee el buzón y **registra qué haría** con cada correo (filas con la etiqueta
«Simulado»), sin responder, sin guardar archivos y sin mover correos. El panel lo avisa con el
recuadro azul **Modo simulación**. Unos días así permiten comparar su panel con lo que archivó el
prototipo antes de cambiar a `real`.

Para pasar a real, ver el paso 4 de [Paso a producción](#paso-a-producción): apagar el prototipo,
fijar `CORTE_CAJA_RECIBIDOS_DESDE` y cambiar `CORTE_CAJA_MODO=real`. El `.env` se lee al arrancar:
**reiniciar el hub** después de cualquier cambio.

### Variables

En `.env` (plantilla en `.env.example`). Sin valores por defecto para credenciales; si falta
alguna obligatoria, la ejecución termina en error con la lista de las que faltan.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `CORTE_CAJA_MODO` | Sí | `simulacion` (registra lo que haría sin responder, guardar ni mover) o `real` |
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
| Revisar ya | Botón **Revisar buzón ahora** en el panel |
| ¿El robot está funcionando? | Revisor: pie de la tarjeta en el inicio ("Última revisión hace 4 min" / "Falló hace…"). Informática: **Administración → Ejecuciones** y **Logs**, con el error técnico y la traza. El panel del módulo no muestra ejecuciones: serían errores técnicos para un actor que no los resuelve |
| Empresas | Panel → **Empresas**: todos los usuarios del módulo la ven; **crear, editar y eliminar solo administradores del hub**. Eliminar solo si ningún correo la usa (si no, se desactiva). También por consola: `flask --app wsgi corte_caja empresas`, `empresa-agregar`, `empresa-modificar` |
| Reintentar un correo con error | Corregir la causa y moverlo en Outlook de `Error` a la bandeja de entrada |
| Reprocesar con otra fecha de referencia | `--param hoy=AAAA-MM-DD` |

Quién ve el panel: quien tenga el módulo asignado en **Usuarios y permisos**. Quién modifica las
empresas: los administradores del hub (`app/core/permisos.py`), porque deciden a qué carpeta va
cada corte. Todo cambio queda en el log (`corte_caja.empresa_*`, con los valores antes y después).

---

## Paso a producción

El prototipo no mueve correos, así que la bandeja de entrada tiene todo el histórico. Por eso el
corte se hace con `CORTE_CAJA_RECIBIDOS_DESDE`.

1. ~~**Base de datos**~~: aplicada el 28/09/2026 (`flask --app wsgi db upgrade`; verificación con
   `flask --app wsgi corte_caja empresas`). Sin ella, el panel responde **500** con
   `Invalid object name 'CORTE_CAJA_CORREOS'` en el log.
2. **Servidor**: `pip install -r requirements-corte_caja.txt` y variables `CORTE_CAJA_*` en `.env`
   con `CORTE_CAJA_MODO=simulacion` y `CORTE_CAJA_RECIBIDOS_DESDE` en el momento de inicio.
3. **Corrida en paralelo (una semana)**: el prototipo sigue operando y el hub simula. Comparar a
   diario el panel (etiqueta "Simulado") con lo que archivó el prototipo. Revisar en especial:
   - correos que el hub rechazaría por **empresa no reconocida** (C5);
   - remitentes internos que el hub marque como externos (dirección X.500 de Exchange no resuelta);
   - fechas futuras o inexistentes.
4. **Corte**:
   1. Detener el prototipo (y su túnel de cloudflared).
   2. `CORTE_CAJA_RECIBIDOS_DESDE` = fecha y hora UTC del último correo que procesó el prototipo.
   3. `CORTE_CAJA_MODO=real`.
   4. Programar la tarea cada 5 min con la cuenta de servicio que tiene permiso de escritura en la carpeta.
5. **Retiro**: archivar el repo del prototipo (hacerlo privado; ver Fase 0 en
   [PLAN_DE_TRABAJO.md](PLAN_DE_TRABAJO.md)).

## Pruebas

`tests/test_corte_caja.py` (49 pruebas): reglas con casos reales de asuntos, archivador
(idempotencia y ruta fuera de la raíz), tarea con `BuzonFalso` (archivado, rechazo escapado y
solo al remitente, ignorados, aislamiento de errores, reintento sin duplicar, simulación sin
efectos ni repeticiones, `RECIBIDOS_DESDE`, configuración incompleta, reversión ante caída), panel
con y sin permiso, CRUD de empresas (solo administradores, validaciones, no eliminar con historial) y CLI.

No cubren: EWS real (resolución de remitentes X.500, creación de subcarpetas, respuesta) ni la
carpeta de red real. Eso se valida en la corrida en paralelo.

## Pendiente con el área usuaria

- Confirmar el rechazo cuando el asunto no nombra la empresa (antes caía en CANELLA).
- Si agencias externas envían desde otros dominios, agregarlos a `CORTE_CAJA_DOMINIOS`.
- Si el correo de confirmación de éxito debe volver a enviarse (en el prototipo estaba deshabilitado; no se migró).
