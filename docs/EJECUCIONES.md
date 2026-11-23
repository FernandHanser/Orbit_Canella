# Ejecuciones y tareas programadas

Cada corrida de una automatización se registra en la tabla `ejecuciones`: módulo, tarea, usuario
o proceso que la inició, inicio, fin, estado (`en_curso`, `exito`, `advertencia`, `sin_cambios`,
`error`, `interrumpida`),
resultado y error. Mientras corre, su `ejecucion_id` se agrega a todos los logs, así que el
detalle de la ejecución muestra su traza completa.

## Desde código

```python
from app.core.ejecuciones import ejecucion

with ejecucion("conciliacion", tarea="conciliar", usuario_id=current_user.id, parametros={"banco": "BI"}) as ctx:
    ctx.log.info("Leyendo estado de cuenta", extra={"evento": "archivo.lectura"})
    ...
    ctx.resultado = {"partidas": 120, "diferencias": 2}   # resumen, no datos sensibles
    if diferencias:
        ctx.estado = "advertencia"
```

Si ocurre una excepción, la ejecución queda en `error` con su traza y la excepción se relanza.

## Tareas declaradas

Una función `tarea(ctx: ContextoEjecucion)` declarada en `DefinicionModulo.tareas` puede
ejecutarse desde la web, la API o la consola con el mismo servicio:

```python
ejecutar_tarea("conciliacion", "conciliar", usuario_id=current_user.id, parametros={...})  # no relanza
```

Los módulos reciben `ResumenEjecucion`, un objeto inmutable con `id`, `estado`, `inicio`, `fin`,
`resultado`, `error`, `usuario_id` e `iniciado_por`; `a_dict()` lo deja listo para JSON. Para
listar corridas anteriores:

```python
from app.core.ejecuciones import ultimas_ejecuciones

ultimas_ejecuciones("conciliacion", usuario_id=current_user.id, limite=10)
```

Nunca consultes el modelo `Ejecucion` desde un módulo: es un detalle interno del núcleo.

## Sin sesión web (tareas programadas)

```bash
flask --app wsgi tareas ejecutar conciliacion conciliar --proceso tarea-diaria-0600 --param banco=BI
```

El log registra `usuario = proceso:tarea-diaria-0600`. Códigos de salida, para que el programador
los distinga: **0** terminó bien (o con advertencia o sin cambios), **1** terminó con error, **3** se omitió
porque el módulo ya tenía una ejecución en curso, **4** se omitió porque el módulo está
deshabilitado en el catálogo. En 3 y 4 no se ejecutó ni se registró nada; queda un evento
`ejecucion.omitida_*` en el log.

Deshabilitar un módulo en **Catálogo de módulos** basta para detener sus tareas programadas: no
hace falta tocar el Programador de tareas de Windows. En Windows se programa con el **Programador de tareas**:

- Programa: `C:\ruta\AUTOMATE_CANELLA\.venv\Scripts\flask.exe`
- Argumentos: `--app wsgi tareas ejecutar conciliacion conciliar --proceso tarea-diaria-0600`
- Iniciar en: `C:\ruta\AUTOMATE_CANELLA`
- Cuenta de servicio con los permisos mínimos (carpetas compartidas, SAP…) y `.env` de producción.

## Ejecución exclusiva por módulo

Un módulo no puede tener dos ejecuciones `en_curso` a la vez, aunque sean de tareas distintas: dos
corridas contables del mismo módulo podrían procesar los mismos datos. Otros módulos no se bloquean.

Al iniciar una ejecución, el núcleo (`_iniciar` en `app/core/ejecuciones.py`):

1. **Colgada (zombie):** si la `en_curso` del módulo empezó hace más de
   `EJECUCIONES_INTERRUMPIDAS_HORAS`, la marca `interrumpida` y deja pasar la nueva.
2. **Vigente:** si hay una más reciente, rechaza la nueva **sin ejecutar ni registrar nada**
   (fail-fast): lanza `EjecucionEnCurso` y deja en el log el evento
   `ejecucion.omitida_por_concurrencia`, con quién la pidió y cuál está en curso.
3. **Carrera:** si dos procesos pasan el paso 2 en el mismo instante, la base decide. El índice
   único filtrado `ux_HUB_EJECUCIONES_modulo_en_curso` (un solo `en_curso` por módulo) hace fallar
   el segundo INSERT, y esa solicitud también recibe `EjecucionEnCurso`. Una consulta seguida de un
   INSERT, aunque estén en la misma transacción, no bastaría: con READ COMMITTED las dos
   solicitudes verían el módulo libre.

Los módulos no implementan nada de esto: solo atrapan `EjecucionEnCurso` para avisar.

```python
from app.core.ejecuciones import EjecucionEnCurso, ejecutar_tarea

try:
    ejecucion = ejecutar_tarea("conciliacion", "conciliar", usuario_id=current_user.id)
except EjecucionEnCurso as exc:
    flash(f"{exc} Espera a que termine.", "warning")        # pantalla
    # API: return jsonify(error="ejecucion_en_curso", mensaje=str(exc)), 409
```

`exc.en_curso` es el `ResumenEjecucion` de la corrida que bloquea (o `None` si terminó justo en ese
instante). El módulo `ejemplo` tiene los dos casos (pantalla y API).

## Corridas sin cambios

Una tarea programada cada pocos minutos (por ejemplo, revisar un buzón) casi siempre no encuentra
nada. Si registrara `exito` cada vez, el historial se llenaría de cientos de filas diarias sin
información. Para eso la tarea marca:

```python
if not pendientes:
    ctx.estado = "sin_cambios"
```

- **Lista de ejecuciones** (Administración): las oculta por defecto ("Con actividad"); se ven con
  el filtro "Todas" o "Sin cambios". `ultimas_ejecuciones()` también las omite, salvo
  `incluir_sin_cambios=True`.
- **Logs**: su `ejecucion.fin` se registra en `DEBUG`.
- **Purga**: al arrancar (es decir, en cada corrida programada) se borran las `sin_cambios`
  terminadas hace más de `EJECUCIONES_SIN_CAMBIOS_DIAS` (7 por defecto). A mano:
  `flask --app wsgi tareas purgar [--dias N]`. Las demás ejecuciones nunca se purgan.
- La salida de `flask tareas ejecutar` es **0**, como un éxito.

Las recientes se conservan para poder comprobar que el programador de tareas sigue corriendo.

## Ejecuciones interrumpidas

Si el servidor se reinicia o el proceso muere a mitad de una tarea, la ejecución no alcanza a
registrar su resultado y quedaría `en_curso` para siempre. Por eso:

- **Al arrancar**, el hub marca como `interrumpida` las ejecuciones que siguen `en_curso` después
  de `EJECUCIONES_INTERRUMPIDAS_HORAS` (2 por defecto), con fecha de fin y el motivo en `error`.
- **A mano**: `flask --app wsgi tareas interrumpidas [--horas N]`.

Solo se marcan las antiguas porque `create_app` también corre en cada comando `flask` (por ejemplo,
una tarea programada) y dos veces con `--debug`. Marcar todas cortaría corridas reales de otro
proceso. **El valor debe ser mayor que la duración de la tarea más larga.** Si una tarea marcada
por error termina después, su resultado real reemplaza a `interrumpida`.

Una ejecución `interrumpida` puede haber dejado efectos externos a medias (un correo enviado, un
archivo movido): revisa su traza en **Ejecuciones** antes de repetirla.

## Procesos largos y cola de tareas

En esta versión las tareas corren de forma síncrona (en la petición o en el proceso de consola).
No hay cola porque ningún módulo la necesita todavía.

Cuando un módulo tenga procesos largos o de escucha continua, el punto de conexión es
`ejecutar_tarea()` en `app/core/ejecuciones.py`:

1. Crear la fila `Ejecucion` en estado `en_curso` y encolar `(modulo_id, tarea, parametros, ejecucion_id)`
   en RQ, Dramatiq o Celery (en Windows, preferir RQ con `SimpleWorker` o Dramatiq).
2. El worker crea la app con `create_app()` y ejecuta la tarea dentro del mismo `ejecucion(...)`,
   reutilizando el identificador para conservar el vínculo con los logs.
3. La web consulta el estado por el id (p. ej. `GET /m/<id>/api/ejecuciones/<ejecucion_id>`).

No se deben iniciar hilos en segundo plano dentro de la aplicación web: con varios workers o
reinicios se duplican o se pierden.
