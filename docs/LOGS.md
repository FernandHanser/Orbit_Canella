# Logs centrales

Toda la aplicación (hub y módulos) usa una única configuración definida en `app/core/logs.py`.

## Formato

Un archivo por día: `LOG_DIR/automate-AAAA-MM-DD.jsonl`, un evento JSON por línea:

```json
{"ts": "2026-09-24T15:58:54.935-06:00", "nivel": "INFO", "modulo": "ejemplo",
 "evento": "demo.preparacion", "mensaje": "Preparando 1 pasos de demostración",
 "usuario": "persona@canella.com.gt", "ejecucion_id": "7fe557bd…", "logger": "automate.ejemplo",
 "datos": {"…": "…"}, "traza": "Traceback … (solo en errores)"}
```

| Campo | Contenido |
|---|---|
| `ts` | Fecha y hora local con zona horaria |
| `nivel` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `modulo` | Id del módulo, o `core` para eventos del hub |
| `evento` | Código estable y filtrable (`auth.acceso`, `ejecucion.fin`…) |
| `usuario` | Correo del usuario en sesión, o `proceso:<nombre>` en tareas sin sesión |
| `ejecucion_id` | Identificador de la ejecución en curso (se inyecta automáticamente) |
| `datos` | Contexto adicional estructurado (saneado) |
| `traza` | Traza completa cuando se registra una excepción |

En consola se imprime una versión legible de la misma información.

Los accesos HTTP del servidor (`werkzeug`: una línea por cada página, CSS, JS o imagen) solo
aparecen en consola. Al archivo, y por lo tanto a **Administración → Logs**, llegan únicamente sus
advertencias y errores.

## Emitir logs desde un módulo

```python
from app.core.logs import get_logger

log = get_logger("conciliacion")            # siempre el id del módulo

log.info("Archivo recibido", extra={"evento": "archivo.recibido", "datos": {"nombre": nombre, "filas": 120}})
log.warning("Partidas sin conciliar", extra={"evento": "conciliacion.diferencias", "datos": {"cantidad": 2}})
try:
    ...
except Exception:
    log.exception("Fallo al leer el estado de cuenta", extra={"evento": "archivo.error"})
    raise
```

No crees handlers, formatos ni archivos propios, y no uses `print` ni `logging.basicConfig`.
Los logs de bibliotecas externas emitidos durante una petición a un módulo se atribuyen a ese
módulo.

## Niveles

| Nivel | Cuándo |
|---|---|
| `DEBUG` | Detalle de pasos, solo útil al diagnosticar (activo en development) |
| `INFO` | Hechos de negocio y del sistema: acceso, ejecución iniciada o finalizada, archivo procesado |
| `WARNING` | Situación anómala recuperable: acceso denegado, dato ignorado, reintento |
| `ERROR` | La operación falló; usar `log.exception` para incluir la traza |
| `CRITICAL` | El hub o un módulo no puede operar |

## Qué no registrar

Contraseñas, tokens, cookies, cadenas de conexión, datos sensibles de Contabilidad (montos de
cuentas o datos personales) ni el contenido de documentos. Registra identificadores, nombres de
archivo y conteos.

Como segunda barrera, el formateador oculta valores con forma `clave=valor` o `clave: valor`
cuando la clave parece sensible (password, contraseña, clave, token, secret, api_key,
authorization, cookie), reemplaza por `***` las claves sensibles en `datos` y recorta mensajes
largos (2000 caracteres; 300 por valor en `datos`). No sustituye el cuidado al escribir el log.

## Configuración por ambiente

| Variable | development | production | Descripción |
|---|---|---|---|
| `LOG_LEVEL` | DEBUG | INFO | Nivel mínimo de los loggers `automate.*` |
| `LOG_RETENCION_DIAS` | 14 | 180 | Se eliminan archivos más antiguos al abrir el del día |
| `LOG_DIR` | `logs/` | `logs/` | Directorio de archivos |
| `LOG_CONSOLA` / `LOG_ARCHIVO` | 1 / 1 | 1 / 1 | Salidas habilitadas |

El handler no renombra archivos, por lo que el servidor web y las tareas programadas pueden
escribir en el mismo directorio a la vez.

## Consulta

- Web: **Administración → Logs** (filtros por módulo, ejecución, nivel, usuario, texto y días) y
  el detalle de cada ejecución.
- Consola: `flask --app wsgi logs buscar --modulo ejemplo --ejecucion <id> --nivel WARNING --dias 7 [--json]`.
- Los archivos JSONL pueden enviarse más adelante a un agregador (Graylog, ELK, Azure Monitor…)
  sin cambiar los módulos.
