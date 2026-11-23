# Plan de integración: Contraseñas de pago

Estado: **propuesta, no ejecutada.** Basado en la rama `dev` de
`RicardoCruzLemus/Automatizacion_Contrasenas` (último commit 24/09/2026). Lo común a los dos
módulos, las acciones urgentes y las decisiones pendientes están en
[PLAN_DE_TRABAJO.md](PLAN_DE_TRABAJO.md).

---

## 1. Qué hace hoy

Los proveedores envían factura y orden de compra (OC) por correo para tramitar su contraseña
de pago. Cada 60 segundos el robot:

1. Lee por **Microsoft Graph** los correos no leídos cuyo asunto contiene el filtro configurado.
2. Descarga los adjuntos (PDF, XML, JPG, PNG de más de 10 KB) a una carpeta temporal.
3. Aplica **OCR** (EasyOCR + Poppler) y extrae con expresiones regulares: NIT, empresa, OC,
   número y total de factura, condiciones de pago y autorizador (este último cruzando el texto con
   la tabla de autorizadores).
4. Consulta **STOD** (SQL Server) con dos procedimientos: valida el proveedor por NIT
   (`CPRO_ValidarProveedor`) y obtiene días de crédito, forma de pago y moneda
   (`CPRO_ObtenerDiasPagoCode`). Calcula la fecha de cheque (el viernes siguiente al vencimiento).
5. Clasifica: **Aceptada**, **Parcial** (falta OC o factura, o el correo dice "parcial") o
   **Rechazada** (no se leyó nada, o esa factura con esa OC ya fue aceptada antes).
6. Archiva en `<Estado>/<Empresa>/<Año>/<DD-MM>/NIT-<nit>/<Autorizador>/OC-<oc>/`, renombra los
   archivos a `OC-<n>.pdf` / `FAC-<n>.pdf`, omite duplicados por hash y genera el comprobante
   `Comprobante_STOD_<oc>.pdf`.
7. Guarda el trámite en SQLite y marca el correo como leído.

Panel: resumen por estado y mantenimiento de la tabla persona → autorizador (agrupada por
jefatura).

## 2. Problemas encontrados

**Seguridad**

1. **Nombres de adjuntos sin sanear.** El nombre que envía el proveedor se usa tal cual para
   escribir en disco (`os.path.join(temp_dir, att["name"])`). Un nombre con `..\` permite escribir
   archivos fuera de la carpeta temporal. Lo mismo aplica a carpetas armadas con texto del OCR
   (una "empresa" leída como `..`).
2. Conexión a STOD como `sa` (según su README) y `SECRET_KEY` con valor por defecto.
3. El log escribe los primeros 1000 caracteres del texto de cada documento (datos de facturas).
4. Panel sin login y formularios sin protección CSRF.

**Funcionamiento**

5. Lee el **buzón personal** de un desarrollador con inicio de sesión interactivo (device code +
   MFA). No sirve para una tarea desatendida en un servidor.
6. Marcar como leído requiere el permiso `Mail.ReadWrite`; la documentación del proyecto solo
   pide `Mail.Read`. Si no se otorgó, el `PATCH` falla sin que el código lo note y el correo se
   vuelve a listar en cada ciclo.
7. Si STOD no responde, el error se registra pero el trámite **sigue y se marca como leído**; el
   README afirma lo contrario ("no marcará el correo como leído").
8. Si no reconoce la empresa, usa en silencio la empresa 1 (Canella) para consultar STOD.
9. OCR sobre todo: rasteriza incluso PDF nativos, que tienen el texto exacto y se leen en
   milisegundos. El modelo de EasyOCR se carga al importar el módulo (lento y con mucha memoria).
10. `requirements.txt` no incluye `pyodbc` ni `fpdf2`; los binarios de Poppler (49 MB) están
    versionados en git.
11. El correo de rechazo al proveedor está descrito pero no implementado.

**Diferencias con la guía para proveedores** (`guia_proveedores.md`)

| La guía dice | El código hace |
|---|---|
| Se acepta "OC: 44021194" | Solo reconoce "Orden de compra número …" |
| Fotos JPG/PNG se rechazan | Las acepta y las intenta procesar como PDF |
| Solo PDF nativos | Aplica OCR como si todo fuera escaneado |
| Un correo con varias facturas se devuelve | No se valida |

## 3. Cómo quedaría en el hub

```text
app/modulos/contrasenas/
├── __init__.py          # MODULO: id "contrasenas", icono "file-invoice", tareas
├── views.py             # trámites (filtros, detalle, descarga del comprobante), autorizadores
├── models.py            # tablas CONTRASENAS_*
├── services/
│   ├── correo.py        # una pasada sobre el buzón (servicio de correo compartido)
│   ├── extraccion.py    # texto directo del PDF y OCR solo como respaldo; regex de negocio
│   ├── stod.py          # procedimientos de STOD sobre la conexión compartida (app/integraciones/stod.py)
│   ├── clasificacion.py # Aceptada / Parcial / Rechazada, duplicados
│   ├── archivo.py       # árbol de carpetas con nombres saneados
│   └── comprobante.py   # PDF del comprobante (fpdf2)
└── templates/contrasenas/
```

**Tarea** `procesar_correos` cada 1–5 minutos, con ejecución exclusiva (el OCR puede tardar más
que el intervalo).

**Tablas:**

| Tabla | Reemplaza a | Notas |
|---|---|---|
| `CONTRASENAS_TRAMITES` | `email_logs` | + ejecucion_id, código de proveedor, fecha de cheque, ruta del comprobante |
| `CONTRASENAS_AUTORIZADORES` | `authorizer_map` | Carga inicial con un comando (`flask contrasenas importar-autorizadores archivo.csv`) en lugar de `seed.py` versionado |

**Mejoras incluidas en la integración**

- Leer primero el texto del PDF (Poppler `pdftotext` o `pypdf`) y usar OCR solo si no hay texto:
  más rápido y exacto para los PDF nativos que pide la guía.
- OCR cargado bajo demanda y dependencias en `requirements-contrasenas.txt`; Poppler instalado
  en el servidor y referido por variable (`CONTRASENAS_POPPLER_PATH`), fuera de git.
- Si STOD falla, el correo queda sin marcar y la ejecución en `error` para reintentarse.
- Empresa no reconocida → trámite **Parcial para revisión**, no Canella por defecto.
- Logs con NIT, OC y estado, sin el texto de los documentos.

**Configuración** (`.env`, sin defaults): `CONTRASENAS_BUZON`, `CONTRASENAS_FILTRO_ASUNTO`,
`CONTRASENAS_STORAGE_DIR`, `CONTRASENAS_POPPLER_PATH`. STOD usa la conexión compartida del hub
(`STOD_*`, ver fase 1 del [plan de trabajo](PLAN_DE_TRABAJO.md)).

## 4. Pruebas

- Extracción con textos de muestra (sin OCR real): NIT excluyendo el de Canella, OC, factura FEL
  de 10 dígitos, total sin confundir con subtotal, condiciones de pago.
- Clasificación: aceptada, parcial por documento faltante, parcial explícita, duplicado.
- Cálculo de fecha de cheque (vencimiento en viernes, fin de semana).
- STOD y Graph simulados; nombres de adjuntos maliciosos (`..\x.pdf`).

## 5. Pendiente de confirmar con el área usuaria

- Si el correo de rechazo al proveedor debe enviarse y con qué texto.
- Reglas de la guía que deben cumplirse de verdad (una factura por correo, rechazo de fotos).
- Quién mantiene la tabla de autorizadores y quién ve los trámites.
- Si la fecha de cheque siempre es viernes y cómo se tratan los feriados.
