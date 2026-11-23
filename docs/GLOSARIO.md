# Glosario y actores

Vocabulario común entre Contabilidad, Informática y el código. Cuando se integra un módulo, se
agrega su sección con sus actores reales y qué puede hacer cada uno. El nombre técnico de un
rol (`admin`, `usuario`) puede ser genérico; el actor que lo usa, no.

---

## Plataforma (núcleo del hub)

Los nombres y descripciones de los roles vienen de `app/core/roles.py` (fuente única); una
prueba verifica que esta tabla coincida. El rol técnico `usuario` se muestra como **Operador**
para no confundirlo con el *usuario STOD*, que es la identidad.

| Término | Significado | En el código |
|---|---|---|
| **Usuario STOD** | La identidad: el nombre con que la persona entra a STOD y al hub. No es un rol. Se guarda en los logs (identificador estable para auditoría), pero no se muestra como nombre | `Usuario.usuario_stod` |
| **Nombre** | Nombres y apellidos reales de la persona. STOD no los guarda: son **obligatorios** al registrarla o editarla en el hub y STOD nunca los sobrescribe. Es lo que se muestra en todo el sistema (menú, saludo, listas, ejecuciones). Quien entró sin prerregistro aparece con un nombre derivado de su correo y la etiqueta «Sin nombre registrado» hasta que se complete | `nombres`, `apellidos`, `nombre_completo` |
| **Persona del hub** | Alguien que inicia sesión con su usuario y contraseña de STOD | Modelo `Usuario` (`HUB_USUARIOS`) |
| **Operador** | Opera los módulos que tenga asignados. No configura nada. En cada módulo recibe el nombre de su actor real (ver abajo) | Rol `usuario` + `HUB_PERMISOS_MODULO` |
| **Administrador** | Asigna módulos, habilita o deshabilita personas, configura los módulos y revisa ejecuciones y logs. | Rol `admin`; contrato `app/core/permisos.py` |
| **Superadministrador** | Todo lo del administrador, más nombrar administradores y habilitar o deshabilitar módulos. Se asigna solo por consola. | Rol `superadmin` |
| **Módulo** | Una automatización contable dentro del hub | `app/modulos/<id>/`, `DefinicionModulo` |
| **Ejecución** | Una corrida de una tarea de un módulo, con su estado y sus logs | `HUB_EJECUCIONES`, `ResumenEjecucion` |
| **Proceso** | Quien inicia una ejecución sin sesión web (Programador de tareas de Windows). Es una etiqueta, no una identidad con permisos | `proceso:<nombre>` |
| **Cuenta de servicio** | Cuenta de Windows con que corre el Programador de tareas; necesita los permisos mínimos sobre carpetas y sistemas del módulo | Fuera del código: se define con Informática |

Reglas de acceso de la plataforma:

- Todo se niega por defecto: sin sesión no se ve nada, y una persona nueva entra como Operador y sin módulos.
- Dar el rol de Administrador pide confirmación: es escalar privilegios.
- Ningún rol da acceso implícito a los módulos, tampoco el de superadministrador.
- La **operación** de un módulo es para sus operadores; su **configuración**, solo para
  administradores del hub. Lo verifica el servidor (403), no solo la interfaz.

---

## Corte de caja diario (`corte_caja`)

### Actores

| Actor | Quién es | Entra al hub | Puede |
|---|---|---|---|
| **Remitente de agencia** | Cajero o encargado de caja que envía el corte por correo desde `@canella.com.gt` | No | Enviar correos al buzón; recibe los rechazos |
| **Revisor de Contabilidad** | Persona de Contabilidad con el módulo asignado | Sí (Operador) | Ver los correos de **todas** las empresas (procesados, rechazados, ignorados, con error), su detalle y la lista de empresas; presionar **Revisar buzón ahora**. **No** puede modificar la configuración del módulo |
| **Administrador del hub** | Informática | Sí (Administrador o Superadministrador) | Todo lo del revisor, más **crear, editar y eliminar empresas** y abrir la ejecución y sus logs desde el detalle |
| **Robot** | La tarea `procesar` ejecutada por el Programador de tareas | No (`proceso:corte-caja-5min`) | Leer el buzón `automatizacionescaja@`, guardar en `\\128.1.200.171\Cortes-de-caja$`, responder rechazos y mover correos |

Decisión del 28/09/2026: **el revisor ve todas las empresas.** No hay alcance por empresa ni
por agencia. Si algún día un revisor solo debe ver sus empresas, se diseña como alcance por
persona en el núcleo, no dentro del módulo.

### Términos

| Término | Significado |
|---|---|
| **Corte de caja** | Archivos (PDF o Excel) con el cierre diario de caja de una agencia |
| **Empresa** | Destino del corte (MAQUIPOS, VESA, Cobradores, Mauto, MR. Credit, CANELLA). Se reconoce por palabras clave del asunto y es la primera carpeta de la ruta |
| **Palabra clave** | Texto que identifica una empresa en el asunto, sin importar mayúsculas ni tildes |
| **Fecha del corte** | Fecha escrita en el asunto; decide la carpeta `Año/Mes/DD-MM-AAAA` |
| **Procesado** | Correo válido: sus adjuntos se guardaron y el correo pasó a la subcarpeta `Procesados` del buzón |
| **Rechazado** | Asunto o adjuntos no válidos: se respondió al remitente explicando qué corregir |
| **Ignorado** | Correo automático o de un remitente externo: no se responde |
| **Con error** | Falla inesperada al procesarlo: se revisa y se devuelve a la bandeja para reintentar |
| **Modo simulación** | El robot registra qué haría sin responder, guardar ni mover |

---

## Expedientes de Seguros (Taller) (`expedientes_seguros`)

### Actores

| Actor | Quién es | Entra al hub | Puede |
|---|---|---|---|
| **Taller (Karen del Cid)** | Conforma y revisa el expediente y lo adjunta en PDF a la llamada en SAP | Opcional (Operador) | Consultar el expediente y armar paquetes |
| **Cajero (Caja Taller)** | Factura y envía el paquete a Créditos y Cobros | Sí (Operador) | Buscar la llamada, marcar páginas, subir la factura, generar el paquete y abrir el correo en Outlook |
| **Créditos y Cobros** | Recibe el correo (Gustavo Estrada, `cobroscanella@`…) y presenta a la aseguradora | No | Recibir el correo |
| **Administrador del hub** | Informática | Sí | Además: aseguradoras, códigos SAP y correo por defecto |

### Términos

| Término | Significado |
|---|---|
| **Llamada de servicio** | Caso del vehículo en SAP (`OSCL.callID`, el «ID Llamada»); trae aseguradora, reclamo, póliza y el expediente adjunto |
| **Centro de costo** | `OSCL.U_CECO` (1602 = Servicios Auto Taller Pintura). No es «TAL-CANE», que es la serie de numeración |
| **Expediente** | PDF completo que Taller escanea (~100 páginas) y adjunta a la llamada. No se modifica nunca |
| **Paquete** | PDF nuevo con las páginas elegidas para Cobros: `<llamada>_<aseguradora>_<fecha>.pdf` |
| **Factura unida / separada** | Según la aseguradora, la factura va como primera página del paquete o como archivo `FAC <llamada>-<aseguradora>.pdf` |
| **Correo por defecto** | Para, CC, asunto y cuerpo que usan todas las aseguradoras en lo que no tengan propio |
| **Checklist** | Documentos que Créditos pide a cada aseguradora (Factura original, Finiquito, DPI…); «si aplica» = opcional. En el visor, cada página se asigna a un documento y el checklist muestra en vivo qué está y qué falta |

