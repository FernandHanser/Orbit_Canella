# Módulo Expedientes de Seguros (Taller) (`expedientes_seguros`)

Estado al 05/10/2026: **implementado y probado con SAP simulado** (49 pruebas). Migraciones hasta
`09e8cd785ea5` aplicadas en `AUTOMATE_CANELLA` (128.1.200.70); el «archivo aparte» por documento
(`c99408375b29`) y la evidencia del DPI (`831fec687c0d`) están probadas en SQLite pero **no
aplicadas aún** en LocalDB ni en 128.1.200.70. Falta la primera prueba con una llamada real y
confirmar el uso real con Caja (ver [Pendiente](#pendiente)).

Requerimiento: *Ficha de iniciación: Optimización de facturación, envío y control de expedientes
de seguros* (sesiones del 17, 22 y 24/09/2026). Material de contexto en `contexto/` (no se
versiona: tiene datos reales).

---

## Qué resuelve

Hoy Karen (Taller) escanea el expediente completo (~100 páginas) y lo adjunta a la llamada de
servicio en SAP. Después Caja recibe la papelería física, factura, **vuelve a escanear** la
selección para Cobros y arma el correo a mano. La ficha pide reducir tiempo y errores sin empeorar
lo que hoy funciona. Jorge Picholá descartó editar el PDF de SAP a mano porque era más lento y
riesgoso que escanear.

El módulo elimina ese reescaneo sin volver a la edición manual:

```text
0. Bandeja  al entrar: llamadas de seguros con expediente y sin paquete → «Armar»
1. Buscar   (o) llamada de servicio + centro de costo (OSCL.U_CECO; 1602 = Taller Pintura)
            → SAP: aseguradora, reclamo, póliza, factura (serie/número) y el PDF del anexo
            (si la llamada trae además el DPI a color como segundo anexo, se combina: ver abajo)
2. Visor    miniaturas de todas las páginas; clic en la página para leerla en grande
            (ajustar al ancho / tamaño real) y decir qué documento del checklist es;
            la casilla la incluye (Mayús+clic: rango) → checklist en vivo a la derecha
3. Generar  51595_ASEGURADORA LA CEIBA, S. A_2026-09-28.pdf con las páginas marcadas
            (+ factura unida o separada, según la aseguradora). El original de SAP no se toca
4. Correo   Caja revisa Para/CC/asunto/cuerpo en el visor → en el paquete, «Enviar correo»
            lo manda por SMTP desde automatizacionescaja@ (Reply-To: quien lo envía), una
            sola vez. Alternativa: borrador .eml para enviarlo desde Outlook
5. Registro quién armó qué, qué páginas, a quién iba, cuánto tardó y cuándo se envió
```

## Decisiones (28/09/2026)

| Decisión | Motivo |
|---|---|
| **Correo como borrador `.eml`** (opción C: después, envío directo si se aprueba) | La ficha exige revisión humana antes de enviar (RF-06). Sale desde la cuenta de Caja, como hoy, y sin credenciales de correo en el hub |
| **Envío directo desde el hub** (22/10/2026, opción C aprobada) | SMTP al Exchange (`128.1.200.106:587`, STARTTLS), como CODA Reports, con el buzón `automatizacionescaja@` (`EXPEDIENTES_SMTP_*`). La revisión humana se mantiene: Caja revisa el correo en el visor y envía con un clic. El `.eml` queda como alternativa. Probar con `flask --app wsgi expedientes_seguros probar-correo <correo>` |
| **Modo prueba / producción** (22/10/2026) | Mientras se ensaya, todo correo va solo a `"Caja Taller1" <cajamauto2@canella.com.gt>` con «[PRUEBA]» en el asunto y los destinatarios reales en el cuerpo; no marca el paquete como enviado. Prueba es lo predeterminado; un administrador lo cambia en **Aseguradoras y correo → Envío de correos**. Se ve en un aviso amarillo en las pantallas del módulo |
| **El correo va a Créditos y Cobros**, no a la aseguradora | Así son los 4 correos reales de Caja (`contexto/*.eml`): Gustavo Estrada, `asistentedecobros@`, `cobroscanella@`, con copia a Pintura, Celso Toledo y Caja Taller2 |
| **Nombre del paquete** `<llamada>_<aseguradora>_<AAAA-MM-DD>.pdf`, sin `#` | Pedido del usuario; el `#` da problemas en correos y rutas. La factura separada conserva el nombre de hoy: `FAC <llamada>-<aseguradora>.pdf` |
| **Miniaturas en el servidor** (pypdfium2) | Los escaneos de la Canon iR-ADV 529 son solo imagen; se ven con la CSP del hub sin JavaScript de terceros. ~20 ms por página, con caché en disco. **PDFium no es seguro con hilos**: los renders se serializan con un candado (dos simultáneos salieron en blanco el 28/09/2026) |
| **La factura la sube Caja** (opcional) | Se imprime después de que Karen pasa el expediente: no está en el PDF de SAP. Serie y número salen de SAP si la factura ya está ligada a la llamada; si no, se escriben |
| **Se mide el tiempo de armado** | La ficha pide comparar con el proceso actual antes de reemplazar el escaneo directo a correo |
| **Los PDF generados se borran a los 7 días** (`EXPEDIENTES_RETENCION_DIAS`); el registro queda | Contienen DPI y tarjetas de circulación (datos personales) |
| **El DPI a color de SAP se combina con el expediente, no lo reemplaza** (05/10/2026) | Confirmado en `ATC1` real: algunas llamadas traen un segundo anexo, mismo `AbsEntry`, nombre empezando en «DPI» (p. ej. `DPI P-828JGG, LLAMADA 82360, RECLAMO 642772.pdf`), siempre PDF. El visor muestra sus páginas junto a las del expediente (dos secciones claramente rotuladas) y el paquete puede tomar hojas de cualquiera. Distinto del documento del checklist «Copia de DPI» (una foto del DPI física que Caja escanea aparte si la aseguradora lo pide) |

## Dónde está cada dato en SAP

Confirmado en `SBO_CANELLA` (128.1.200.167) con la llamada **51595**:

| Dato | Origen | Ejemplo |
|---|---|---|
| Llamada / orden | `OSCL.callID` / `OSCL.DocNum` | 51595 / 100129274 |
| Aseguradora | `OSCL.customer` / `custmrName` | C000078 / ASEGURADORA LA CEIBA, S. A. |
| Reclamo / póliza | `OSCL.U_Reclamo` / `OSCL.U_Poliza` | 202604763 / 0224103497-14 |
| Centro de costo | `OSCL.U_CECO` → `OPRC.PrcName` | 1602 SERVICIOS AUTO TALLER PINTURA ("TAL-CANE" es la serie de numeración, `NNM1`) |
| Expediente | `OSCL.AtcEntry` → `ATC1` (`trgtPath\FileName.FileExt`) | `\\Srv-sapcanella\archivos-sap\Documentos_SAP\51595.pdf` (`Srv-sapcanella` = **128.1.200.167**, el mismo servidor de SAP; 128.1.200.122 es SRV-TSMAUTO, el escritorio remoto) |
| Factura | **Desde la entrega**: `SCL4` (`Object = 15`) → `INV1` (`BaseType = 15`) → `OINV`, igual que el Tablero de Facturación; también la ligada directo (`Object = 13`). Sin anuladas; se sugiere la de la aseguradora (`CardCode = OSCL.customer`) porque puede haber otra por el deducible | Serie y número FEL en **`U_DoctoSerie` / `U_DoctoNo`** (confirmado el 28/09/2026: llamada 68267 → factura 3151202 de MAPFRE, Serie 87BC5934, Número 3581693582, la del correo real). La 51595 tiene 4 entregas y ninguna factura directa: por eso el camino por entrega |

## Estructura

```text
app/modulos/expedientes_seguros/
├── __init__.py        MODULO: id "expedientes_seguros"
├── sap.py             contrato RepositorioSap + SapSql (solo lectura, pyodbc)
├── documentos.py      miniaturas (pypdfium2) y armado del PDF (pypdf)
├── reglas.py          nombres de archivo, rangos de páginas, plantilla y .eml (puras)
├── servicios.py       casos de uso, cachés (original en memoria, miniaturas en disco) y registro
├── views.py           buscar, visor, imagen de página, generar, paquete, descargas
├── aseguradoras.py    configuración del correo (solo administradores del hub)
├── configuracion.py   variables EXPEDIENTES_*
├── models.py          EXPEDIENTES_SEGUROS_ASEGURADORAS, _CODIGOS, _DOCUMENTOS, _PARAMETROS, _PAQUETES
├── static/            visor.js/.css, checklist.js/.css (editor), inicio.js
└── templates/expedientes_seguros/
```

## Buscador (elemento principal)

Arriba, a todo el ancho, con el logo de SAP. Mientras se escribe el número, **revisa primero las
pendientes**, que ya están cargadas en la página. Si la llamada está ahí, muestra
«✓ Está en tus pendientes · cliente · abierta hace N días · Armar →»; si no, avisa que se buscará en
SAP. Al buscar o dar clic en «Armar» aparece la **pantalla de carga** del hub («Buscando la llamada
51595 en SAP…», con el logo de SAP), y el visor entra con un fundido suave.

## Bandeja de pendientes

Al entrar al módulo se ven las llamadas **pendientes de armar** (decisión del 28/09/2026, opción C):

- **Llamadas activas** del centro de costo (1602), `OSCL.status <> -1` (en SAP B1, -1 = cerrada), **que
  tienen el expediente PDF** en sus anexos (`ATC1`). Sin ventana de días y sin filtrar por
  `U_Tipo`. Decisiones del 28 y 29/09/2026: reemplazan a «hoy o ayer» y a `EXPEDIENTES_BANDEJA_DIAS`,
  que se eliminó. Las llamadas sin PDF no aparecen, porque no hay nada que armar; al adjuntarlo en
  SAP entran solas. Solo las que tienen **paquete generado** en el hub
  salen de la bandeja. Se vacía sola a medida que Caja arma.
- De la más antigua a la más reciente, con la antigüedad **desde que se abrió la llamada**
  (`OSCL.createDate`): verde (hoy o ayer), amarillo (2–3 días), rojo (4 o más). Apoya el control
  de fechas de recepción (RF-09). La columna Expediente muestra la fecha del PDF más reciente.
- Filtro por cliente, paginación de 15 y botón **Armar →** que abre el visor.
- Al lado: el buscador para cualquier otra llamada y la lista de **Armados hoy**. El historial
  completo está en **Historial**.
- El cruce "sin paquete" se hace en el hub (SAP y el hub están en bases distintas). Si SAP no
  responde, la bandeja lo avisa y el buscador sigue funcionando.
- Por validar en SAP: que `status = -1` sea el único estado de cerrada (los estados de llamada se
  pueden personalizar en `OSCS`).

## Checklist en vivo

Cada aseguradora tiene el checklist de Créditos (sembrado desde el libro «CHECK DE DOCUMENTOS PARA
CREDITOS», 15 hojas, 198 documentos; «si aplica» = no obligatorio). En el visor:

1. **Clic en la miniatura** abre la página en grande, legible: 1400 px, **Ajustar al ancho** o
   **Tamaño real**, con ← → para recorrer. La casilla de la esquina la incluye en el paquete.
2. **«Esta página es…»** asigna la página a un documento del checklist y la marca para el paquete.
   La miniatura muestra el documento asignado. **Un documento puede ocupar varias páginas**: se
   asigna a cada una; **«Igual que la pág. anterior»** (tecla A) lo repite sin volver a elegirlo, y
   el checklist muestra el rango («pág. 19-20»).
3. **En la vista grande, el checklist va al lado de la página**, con barra de avance
   («8 de 11 · 73 %»): clic en un documento asigna la página actual (clic de nuevo, la quita).
   Primero los obligatorios con su estado; los «si aplica» abajo en gris y **fuera del porcentaje**.
   **Lo que se ve es lo que va en el paquete:** asignar un documento incluye la página, y quitar
   una página del paquete (casilla, Ninguna, Invertir o el botón del modal) le quita sus documentos
   y su etiqueta. El formulario no se autocompleta en el navegador: solo el borrador lo restaura.
   Una página puede tener **varios documentos** (DPI y tarjeta en la misma hoja): cada clic agrega o
   quita solo ese. Los «si aplica» incluidos se muestran aparte («+1 si aplica»).
   Lo asignado a **la página que se ve** resalta (☑ azul, negrita, barra a la izquierda): un clic lo
   activa y otro clic lo desactiva. El ✓ verde, en cambio, significa que el documento ya está en
   otra página.
   **Cancelar** descarta **toda la selección** (todas las páginas y sus documentos) y cierra la
   vista grande: es cancelar el armado. Lo confirma el modal del hub, apilado encima del visor
   («¿Cancelar el armado del expediente?», **Sí, cancelar todo** en rojo, foco en Cancelar). No
   tiene atajo de teclado, para que no se dispare por accidente. Para quitar un documento de una
   página, basta otro clic en el checklist.
   Pie: **Cancelar** a la izquierda; a la derecha, **Igual que la anterior** (A) y, al final, la
   navegación (‹ 3 de 30 ›). El botón «Incluida / Incluir en el paquete» (Espacio) se quitó el
   29/09/2026 porque confundía. En la vista grande, incluir una página es asignarle un documento; al
   quitarle el último, sale del paquete. La casilla de la miniatura sigue incluyendo o quitando
   páginas sueltas.
4. El panel **Checklist** de la pantalla (con la misma barra) se actualiza solo: ✓ verde con las páginas donde está, ✗ rojo «Falta» en
   los obligatorios, gris «si aplica» en los opcionales, y el contador «N de M obligatorios».
   «Factura original» se cumple al adjuntar el PDF de la factura.
   **También asigna, sin abrir las páginas:** con páginas marcadas que aún no tienen documento,
   aparece «Págs. 12-13: clic en el documento que son», y un clic en el documento se lo asigna a
   todas. Es la misma selección que la de la vista grande (los mismos campos `doc_<n>`): lo que se
   asigna aquí aparece al abrir la página, y al revés.
   Miniaturas: **azul** = marcada, falta decir qué es; **verde** = marcada y con documento asignado.
   **Checklist completo:** al cumplirse el último obligatorio aparece un modal verde,
   «Checklist completo», también encima de la vista grande. Tiene dos opciones:
   **Seguir revisando** e **Ir al correo**, que cierra los modales y lleva a la tarjeta del correo
   con el cursor en «Para». Sale una vez, al pasar de incompleto a completo; no al cargar ni en
   cada clic. El panel del checklist conserva el botón **Ir al correo** mientras esté completo.
   **Cancelar** está en el pie del panel y en la vista grande. Es el mismo componente
   (`data-cancelar-armado`), con la misma confirmación, y está deshabilitado si no hay nada
   marcado.
   **Descartar y empezar de nuevo** (aviso de trabajo recuperado) confirma en rojo y ya no vuelve a
   guardar el borrador al recargar.
   **Sello:** la página ampliada que ya tiene documento muestra en la esquina superior derecha, en verde,
   «✓ Asignada como PRESUPUESTO AUTORIZADO». No bloquea la lectura ni los clics.
   **Un segundo documento en la misma página se consulta:** si la página ya es «X» y se hace clic
   en otro documento, el modal pregunta «¿La página 4 también es «Y»?». Solo se agrega si se
   confirma, que es el caso de una hoja con DPI y tarjeta. Si fue un error, se quita primero «X».
   **Modal sobre modal:** el hub apila cualquier modal que se abre con otro abierto
   (`interaccion.js`, `.modal-apilado`).
5. Al generar, si falta algún obligatorio o la factura, el modal de confirmación del hub dice
   exactamente qué falta. No bloquea: puede haber excepciones que Caja conoce.
6. El paquete guarda el checklist (documento, páginas, presente o faltó) como evidencia. Se
   guardan nombres, no ids: editar el checklist después no altera paquetes anteriores.

El checklist se edita en **Aseguradoras y correo → «N documentos»** (o **Editar → Editar checklist**),
solo administradores. Es una tabla con una fila por documento:

| Acción | Cómo |
|---|---|
| Agregar | «Agregar documento» (fila nueva al final) |
| Renombrar | En la misma fila |
| Obligatorio / si aplica | Interruptor *Obligatorio* |
| Inactivar | Interruptor *Activo*: deja de aparecer en el visor sin borrarse; se reactiva cuando haga falta |
| Ordenar | ↑ ↓ (es el orden del visor) |
| Archivo aparte | Interruptor *Archivo aparte*: ese documento sale en su propio PDF en vez de ir unido al principal (antes solo existía para la factura, como columna de la aseguradora; ahora es por documento, aquí) |
| Quitar | Papelera: la fila queda en rojo y al guardar se pide confirmación |

Se guarda todo con **Guardar checklist**. Los paquetes ya generados no cambian (guardan nombres). La ficha (sección 4.1) advierte diferencias entre este
checklist y la matriz 2026: se sembró el checklist porque es el que usa Créditos, y el dueño de la
matriz debe conciliarlo.

## Correo y aseguradoras

- **Correo por defecto** (Aseguradoras y correo → Editar): Para, CC, asunto y cuerpo que usan
  todas las aseguradoras. Sembrado con los destinatarios, el asunto
  `{aseguradora}//Serie: {serie} Número: {numero}//CANELLA` y el cuerpo de los correos reales.
- **Por aseguradora**: solo lo que cambia (vacío = por defecto). En el formulario va en su propia
  tarjeta, **Correo propio (Opcional)**, con borde celeste y separada de los datos de la aseguradora.
  En la vista previa, lo vacío muestra el valor del correo por defecto, en gris y marcado
  «· por defecto». Sembradas las 15 de la matriz 2026,
  con el código de socio de su checklist. MAPFRE y El Roble, con la fila «Factura original» de su
  checklist marcada **archivo aparte** (ver tabla arriba: ya no es una casilla de la aseguradora,
  es del documento). General, con reclamo y póliza en el asunto.
- **Varios códigos por aseguradora** (RF-01): MAPFRE y La Ceiba tienen dos según la ficha; se
  agrega el segundo al editarla.
- Variables de las plantillas: `{aseguradora}`, `{serie}`, `{numero}`, `{reclamo}`, `{poliza}`,
  `{llamada}`, `{orden}`. Solo se reemplazan esas (sin `str.format`).
- En el visor, Caja ve el correo ya armado y puede cambiarlo antes de generar.
- **Edición amigable** (`static/correos.js`, `templates/expedientes_seguros/_correo.html`), igual
  en el correo por defecto, en cada aseguradora y en el visor:
  - Para y CC son **fichas**: se escribe un correo y se confirma con Enter (o coma, punto y coma,
    espacio o al salir del campo). La ✕ lo quita, y Retroceso con el campo vacío quita el último.
    Pegar una lista la separa sola. Una dirección mal escrita queda en rojo.
  - **Una barra de datos** (+ Aseguradora, + Serie de factura…) sobre el asunto y el cuerpo: inserta
    `{variable}` donde está el cursor del último campo tocado. «Insertar dato en **Asunto**» dice
    cuál. Agrega el espacio que falte antes y después, para que no queden pegadas.
  - **Una vista previa**, «Así llegará el correo», con el asunto y el cuerpo juntos y los datos de
    la llamada 51595 resaltados, en vivo. Quien no es técnico ve el resultado, no las llaves.
  - Por debajo sigue viajando el texto `a; b; c` en el mismo campo, y el servidor lo valida igual
    (`reglas.correo_invalido`). Sin JavaScript, el formulario funciona como antes.

## Si la sesión vence mientras se arma

El visor guarda un **borrador** en el navegador (páginas marcadas, documento de cada página y el
correo) mientras se trabaja. Si la sesión vence, al volver a entrar se regresa a la misma llamada y
aparece «Recuperamos tu trabajo» con **Descartar y empezar de nuevo**. La factura adjunta no se puede
restaurar (el navegador no lo permite): hay que volver a adjuntarla. El borrador dura 12 horas y
se borra al generar el paquete.

## Factura

Si la llamada tiene varias facturas (por ejemplo, la de la aseguradora y la del deducible al
asegurado), el visor muestra **Factura en SAP** para elegir; al elegir, llena Serie y Número. Si
ninguna es de la aseguradora, lo advierte. Si no hay factura ligada, se escriben a mano.

## Validaciones antes de generar (CA-03)

Al menos una página; Serie y Número de la factura; al menos un destinatario; direcciones válidas;
asunto; factura (si se sube) debe ser PDF de hasta 20 MB. Si falta algo, el visor vuelve con los
errores y las páginas que ya estaban marcadas.

## Acceso (CA-08)

| Actor | Puede |
|---|---|
| Cajero / Karen (operador con el módulo asignado) | Buscar, ver, marcar, generar, descargar y abrir el correo |
| Administrador del hub | Además: aseguradoras, códigos y correo por defecto |
| Sin el módulo | Nada: ni pantallas ni imágenes de páginas (403) |

## Configuración

| Variable | Obligatoria | Descripción |
|---|---|---|
| `EXPEDIENTES_SAP_SERVIDOR`, `_BASE`, `_USUARIO`, `_CONTRASENA` | Sí | SBO_CANELLA en 128.1.200.167. Hoy `usrsap` (provisional): pedir un login **solo lectura** sobre `OSCL`, `SCL4`, `OINV`, `ATC1`, `OPRC` |
| `EXPEDIENTES_SAP_DRIVER` | No | `ODBC Driver 17 for SQL Server` |
| `EXPEDIENTES_ANEXOS_SERVIDOR` | No | IP o nombre del servidor de archivos visto desde el hub. SAP guarda `\Srv-sapcanella\…`, nombre que solo resuelve dentro del escritorio remoto SRV-TSMAUTO (128.1.200.122). Hoy: `128.1.200.167` (lectura sin credenciales, verificado el 28/09/2026) |
| `EXPEDIENTES_SAP_CAMPO_SERIE` / `_NUMERO` | No | Campos FEL de `OINV`: `U_DoctoSerie` / `U_DoctoNo` (confirmados) |
| `EXPEDIENTES_CECO_POR_DEFECTO` | No | 1602 |
| `EXPEDIENTES_RETENCION_DIAS` | No | 7 |

La cuenta que corre el hub necesita **lectura** en `\\Srv-sapcanella\archivos-sap`.
Dependencias: `pip install -r requirements-expedientes_seguros.txt` (pypdf, pypdfium2, Pillow).

## Pruebas

`tests/test_expedientes_seguros.py` (35): reglas (nombres, rangos, plantilla segura, direcciones,
`.eml`), PDF (orden de páginas, factura antepuesta, miniatura JPEG), visor y caché de la ruta,
búsquedas fallidas (no existe, otro centro de costo, sin PDF, SAP caído sin 500), generación y
descargas (incluida ruta maliciosa), factura unida o separada, validaciones, plantilla propia y por
defecto, retención, permisos y CRUD de aseguradoras con dos códigos.

No cubren SAP real ni la carpeta del servidor de archivos: se prueban con la primera llamada real.

## Pendiente

1. ~~Confirmar los campos FEL~~: confirmados el 28/09/2026 (`U_DoctoSerie` / `U_DoctoNo`) con la factura 3151202 de MAPFRE.
2. **Permiso de lectura** de la cuenta del hub en `\\Srv-sapcanella\archivos-sap`.
3. **Login de SAP solo lectura** para reemplazar `usrsap`.
4. **Segundo código** de MAPFRE y La Ceiba.
5. Validar con Jorge Picholá y medir el tiempo de armado contra el escaneo directo (ficha 4.2).
6. Definir con Gustavo Estrada el seguimiento posterior (RF-08 a RF-11: entrega física, rechazos,
   reprocesos), fuera de esta primera versión.
