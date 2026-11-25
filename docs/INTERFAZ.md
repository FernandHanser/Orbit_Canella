# Interfaz

La interfaz usa [Tabler 1.5.1](https://tabler.io) y [Tabler Icons 3.48.0](https://tabler.io/icons),
servidos desde `app/static/vendor/` (sin CDN). Todo el texto visible está en español.

---

## Plantillas base

| Plantilla | Uso |
|---|---|
| `base_layout.html` | Esqueleto HTML: `<head>`, CSS/JS de Tabler, favicon. Bloques `titulo`, `head_hub` (solo lo usa `base.html`), `head`, `clase_body`, `cuerpo`, `scripts` |
| `base.html` | Pantallas con sesión: menú lateral, encabezado, mensajes y pie. **La que extienden los módulos.** Bloques `titulo`, `encabezado`, `contenido` (+ `head`, `scripts`) |
| `base_publica.html` | Pantallas sin sesión (login y errores sin sesión): logo animado, título y fondo |
| `_macros.html` | Componentes reutilizables (abajo) |

Variables disponibles en todas las plantillas: `NOMBRE_PRODUCTO`, `SUBTITULO_PRODUCTO`
(definidos en `app/__init__.py`), `modulos_menu` (módulos del usuario), `current_user`,
`config` y `csrf_token()`.

---

## Menú lateral que se oculta

En pantallas grandes, el ícono junto a la marca (`ti-layout-sidebar-left-collapse`, con su texto en
el `title` y el `aria-label`) o **Ctrl + B** desliza el menú fuera de la vista y el contenido ocupa
todo el ancho. Queda un ícono fijo arriba a la izquierda para mostrarlo de nuevo. En celular no aplica: Tabler ya pliega el menú con su botón.

- La preferencia se guarda en el navegador (`localStorage`, clave `orbit.menu`), no en el servidor:
  es una comodidad de pantalla. Se sincroniza entre pestañas abiertas.
- `static/js/menu.js` se carga en `<head>` sin `defer` para poner la clase `menu-oculto` en
  `<html>` antes de pintar; si no, el menú aparecería y desaparecería en cada navegación.
- Va en el bloque `head_hub`, no en `head`: varias pantallas de módulos reemplazan `head` sin
  `super()`, y el menú no debe depender de que lo recuerden. Un módulo **no** usa `head_hub`.
- Oculto, el menú queda con `visibility: hidden`: el tabulador no recorre enlaces invisibles.
- Prueba: `tests/test_interfaz.py::test_menu_se_puede_ocultar_en_todas_las_pantallas_con_menu`.

---

## Macros (`_macros.html`)

```jinja
{% from "_macros.html" import encabezado, campo, interruptor, estado_ejecucion, nivel_log, paginacion as pie_paginacion %}
```

| Macro | Qué dibuja |
|---|---|
| `encabezado(titulo, pretitulo, pretitulo_url=None)` | Encabezado de página. Con botones a la derecha: `{% call encabezado("Título") %}<a class="btn">…</a>{% endcall %}`. Con `pretitulo_url`, el pretítulo (el nivel de arriba, p. ej. la lista) es un enlace a él |
| `campo(form.campo, ayuda=None, autocomplete=None, autofocus=False, revelar=False)` | Campo de formulario WTForms con etiqueta, errores y ayuda. Con `revelar=True` (contraseñas) agrega el botón del ojo para mostrar lo escrito (`data-revelar-contrasena`, ver abajo). Los validadores llevan siempre su mensaje en español (`DataRequired(message=…)`): sin él, WTForms responde en inglés |
| `interruptor(form.campo_booleano, ayuda=None)` | Casilla tipo switch |
| `estado_ejecucion(estado)` | Etiqueta de color para `exito`, `advertencia`, `error`, `en_curso` |
| `nivel_log(nivel)` | Etiqueta de color para niveles de log |
| `avatar_persona(usuario, tamano="")` | Avatar circular de una persona con sus **iniciales** (primer nombre + primer apellido; sin nombre registrado, las dos primeras letras del usuario STOD) sobre un color fijo derivado del usuario STOD. STOD no tiene fotos. Tamaños: `xs`, `sm`, `md`, `lg`, `xl`. Se usa en el menú lateral, la lista de usuarios y el detalle de una persona |
| `paginacion(pagina, "nombre")` | Pie de tarjeta con "Mostrando X–Y de N" y botones de páginas (ver [AGREGAR_MODULO.md](AGREGAR_MODULO.md#listas-largas-paginación)) |
| `mensajes()` | Mensajes `flash()`; ya incluido en `base.html` |

Mensajes al usuario desde una vista: `flash("Texto", "success" | "danger" | "warning" | "info")`.

Filtro de fechas: `{{ valor|fecha }}` o `{{ valor|fecha("%d/%m/%Y %H:%M:%S") }}`; convierte de
UTC (como se guardan) a la hora local.

---

## Tarjetas de módulos (inicio)

Bajo el título **Mis automatizaciones**, una tarjeta por módulo asignado y habilitado:

| Parte | Contenido | Por qué |
|---|---|---|
| Ícono y nombre | Nombre en mayúsculas (`|upper`) | Reconocer el módulo sin leer |
| Descripción | Una o dos líneas, en verbos | Recordar qué hace; la explicación larga va dentro |
| Pie | Punto de estado + última ejecución relativa ("hace 4 min", fecha exacta al pasar el mouse) y **Abrir →** | Saber que el robot sigue vivo; señal de que la tarjeta se abre, también en pantallas táctiles |

Colores del punto: verde = bien o sin cambios, amarillo = advertencias, rojo = falló, azul
animado = en curso, naranja = interrumpida. Toda la tarjeta es el enlace (área de clic grande), y
las de una misma fila tienen la misma altura.

---

## Colores por estado

Un mismo estado usa siempre el mismo color, en pestañas, contadores, etiquetas y detalle:

| Color | Significado | Ejemplos |
|---|---|---|
| Verde | Terminó bien | Procesado, éxito, habilitado |
| Amarillo | Requiere revisar, pero no falló | Rechazado, advertencia |
| Rojo | Falló | Con error, error |
| Gris | Sin acción / neutro | Ignorado, sin cambios, deshabilitado |
| Azul | En curso o informativo | En curso, simulación |

Pestañas por estado (ejemplo: Corte de caja): el **ícono** lleva siempre su color, el
**contador** solo cuando es mayor que 0 (un 0 no debe llamar la atención) y la pestaña activa se
subraya con su color (clase `pestana-estado` + `style="--color-pestana: var(--tblr-<color>)"`).
El color nunca es la única señal: ícono y texto se mantienen.

---

## Expiración de la sesión

Lo decide el servidor (`app/core/sesion.py`) y lo avisa el navegador (`static/js/sesion.js`,
cargado en toda pantalla con sesión). Ningún módulo tiene que hacer nada.

| Qué | Cómo |
|---|---|
| **Inactividad** | `SESION_INACTIVIDAD_MINUTOS` (60) sin peticiones cierra la sesión. Cada petición la renueva, salvo la consulta del aviso |
| **Jornada máxima** | `SESION_MAXIMA_HORAS` (10) desde el inicio de sesión, aunque haya actividad: obliga a validar de nuevo con STOD |
| **Aviso previo** | A `SESION_AVISO_SEGUNDOS` (120) del final: modal con cuenta regresiva, **Extender sesión** y **Cerrar sesión**. Si vence la jornada no se puede extender: solo **Entendido**, que cierra el aviso hasta el final y deja una cuenta pequeña abajo a la derecha (`.sesion-cuenta-mini`) para guardar con calma. La cuenta del modal no lleva `aria-live` (se anunciaría cada segundo) |
| **Varias pestañas** | Sincronizadas: extender o navegar en una actualiza el aviso de las demás. Antes de mostrarlo se consulta al servidor el tiempo real |
| **Al vencer** | Login con `?motivo=inactividad` / `jornada` / `stod` / `formulario` y un mensaje claro, y `?siguiente=` para volver a la misma página |
| **Formulario enviado con la sesión vencida** | Lleva al login con el motivo, no a un «400 Bad Request» |
| **Trabajo en curso** | Evento `sesion:vence` antes de salir. El visor de Expedientes guarda un borrador (páginas, documentos y correo) y lo restaura al volver a la llamada |
| **API** | 401 JSON con `error="sesion_vencida"` y el motivo |

Un módulo con un formulario largo puede escuchar `sesion:vence` (o guardar mientras se edita)
para no perder el trabajo, como `app/modulos/expedientes_seguros/static/visor.js`.

---

## Spinners y confirmaciones

Principio: **no hacer pensar al usuario**. Toda acción que tarde debe mostrar que se está
procesando, y toda acción con efectos que no se deshacen debe pedir confirmación antes. Lo
resuelve el núcleo (`static/js/interaccion.js`, cargado en todas las páginas; el modal compartido
está en `base.html`). Un módulo solo agrega atributos al `<form>`, sin escribir JavaScript:

```jinja
<form method="post" action="{{ url_for('corte_caja.procesar_ahora') }}"
      data-cargando="Revisando buzón…"
      data-confirmar-titulo="¿Revisar el buzón ahora?"
      data-confirmar="Se enviarán los correos de rechazo a las agencias…"
      data-confirmar-boton="Sí, revisar">
```

| Atributo | Efecto | Cuándo usarlo |
|---|---|---|
| `data-cargando="Texto…"` | Al enviar, deshabilita los botones del formulario y muestra un spinner con el texto. Ignora clics repetidos. **También en un enlace `<a>`** que abre una página lenta (consulta SAP u otro sistema): el enlace muestra el spinner y no admite otro clic | **Siempre** que la acción pueda tardar más de un segundo (ejecutar tareas, consultar sistemas externos) |
| `data-revelar-contrasena` (en un `<button>` con `aria-controls` = id del campo) | Alterna entre mostrar y ocultar la contraseña (ícono `ti-eye` / `ti-eye-off`, `aria-pressed` y `aria-label` cambian con él). Al enviar el formulario se vuelve a ocultar. El ojo propio de Edge (`::-ms-reveal`) se oculta en el CSS para que no haya dos | Lo arma `campo(..., revelar=True)`; no escribirlo a mano |
| `data-confirmar="Mensaje"` (+ `-titulo`, `-boton`) | Abre el modal de confirmación; solo envía si el usuario confirma. Con `data-confirmar-si="<selector CSS>"` solo confirma si algo del formulario coincide (p. ej. `input[name=rol][value=admin]:checked`) | Solo para efectos **irreversibles o hacia terceros**: enviar correos, mover o borrar datos, escribir en SAP. No en acciones de solo lectura: un modal innecesario entrena a ignorarlo |

El mensaje del modal debe decir **qué va a pasar** (qué se envía, qué se mueve, a quién), no
solo "¿Está seguro?", y no puede prometer nada que el sistema no haga. La confirmación puede
depender del estado: en Corte de caja solo aparece en modo real, porque en simulación la
revisión no tiene efectos.

**Pantalla de carga** (`data-cargando-pagina="Mensaje…"` en un formulario con `data-cargando` o en un
enlace): además del spinner del botón, cubre la página con el mensaje hasta que llega la siguiente.
Tiene una segunda línea opcional (`data-cargando-detalle`) y un logo opcional (`data-cargando-logo`,
p. ej. el de SAP). Aparece con 0.25 s de retraso para no parpadear si la respuesta es inmediata. Se
usa en esperas que se sienten, como consultar SAP o leer un PDF: en Expedientes, al buscar una
llamada y al dar clic en «Armar».

El modal abre con el foco en **Cancelar** (un Enter accidental no ejecuta la acción), se cierra
con Esc o con la ✕, y bloquea el resto de la página mientras está abierto. Un formulario ya
enviado ignora clics repetidos.

Desde JavaScript, el mismo modal se abre con `window.hub.confirmar({titulo, mensaje, boton,
peligro, devolverFoco, alConfirmar})`. `peligro: true` lo pinta en rojo para acciones que
descartan trabajo. Si ya hay otro modal abierto, se **apila encima**: su propio fondo lo cubre
(`.modal-apilado` en `automate.css`) y, al cerrarse, el foco vuelve al modal de abajo. No hay que
armar confirmaciones propias dentro de un modal.

### Dónde se aplica

| Pantalla | Spinner | Confirmación |
|---|---|---|
| Inicio de sesión | "Validando con STOD…" | — |
| Administración → Registrar / editar persona | "Guardando…" | Solo al dar el rol de Administrador (escalar privilegios) |
| Catálogo → Sincronizar | "Sincronizando…" | — |
| Catálogo → Deshabilitar módulo | "Deshabilitando…" | Sí: bloquea el módulo para todos y detiene sus tareas programadas |
| Catálogo → Habilitar módulo | "Habilitando…" | — |
| Logs → Filtrar | "Buscando…" (lee archivos) | — |
| Corte de caja → Revisar buzón ahora | "Revisando buzón…" | Solo en modo real |
| Corte de caja → Empresas (guardar / eliminar) | "Guardando…" / "Eliminando…" | Solo eliminar |
| Ejemplo → Ejecutar | "Ejecutando…" | — |
| Expedientes → Armar → (enlace de la bandeja) | "Abriendo…" | — |
| Expedientes → Filtrar por aseguradora / Buscar llamada | "Filtrando…" / "Buscando en SAP…" | — |
| Expedientes → miniaturas y vista ampliada | Spinner en cada página hasta que llega; aviso si no carga | — |
| Expedientes → Generar paquete | "Generando paquete…" | Solo si **falta un documento obligatorio del checklist o la factura**: el mensaje lo arma `visor.js` con lo que falte (`data-confirmar-si="#advertencias[data-hay]"`) |
| Expedientes → Correo por defecto (guardar) | "Guardando…" | Sí: cambia el correo de todas las aseguradoras sin correo propio |
| Expedientes → Eliminar aseguradora | "Eliminando…" | Sí |
| Expedientes → Visor → Cancelar | — | Sí (`hub.confirmar`, rojo, encima del visor): descarta toda la selección |
| Expedientes → Guardar checklist | "Guardando…" | Solo si hay documentos **marcados para quitar** (`data-confirmar-si="input[data-quitar]:checked"`); inactivar no pregunta |

Lo verifica `tests/test_interfaz.py`. Pantalla nueva con un botón que ejecuta algo: agregarla a
esta tabla.

---

## Archivos estáticos: `estatico()`

```jinja
<img src="{{ estatico('img/mi_imagen.png') }}">
```

Úsalo en lugar de `url_for('static', ...)` para archivos de `app/static/`. Agrega la fecha del
archivo a la URL (`?v=...`), así que **al reemplazar un archivo con el mismo nombre el navegador
descarga la versión nueva** sin necesidad de Ctrl+F5.

Las URLs escritas dentro de un `.css` (`url(...)`) no se versionan; por eso las imágenes que
cambian a menudo (como el fondo) se asignan desde la plantilla.

Estáticos propios de un módulo: `url_for('<id>.static', filename=...)` (ver
[AGREGAR_MODULO.md](AGREGAR_MODULO.md#6-archivos-estáticos-del-módulo)).

---

## Reglas de la CSP

La política de seguridad (`app/core/seguridad.py`) solo permite recursos del propio sitio:

- **Sin JavaScript inline**: nada de `<script>…</script>` con código ni `onclick="…"`. El JS va
  en archivos `.js` cargados con `<script src="…">` en el bloque `scripts`.
- **Sin CDN**: fuentes, CSS, JS e imágenes se copian a `static/` (o al `static/` del módulo) con
  la versión en el nombre de la carpeta, y se registran en `app/static/vendor/README.md`.
- Los estilos inline (`style="…"`) sí están permitidos.

---

## Íconos

`<i class="ti ti-<nombre>"></i>` con cualquier nombre de https://tabler.io/icons. El ícono de un
módulo se declara en `DefinicionModulo(icono="<nombre>")` sin el prefijo `ti-`.

---

## Identidad visual actual

| Elemento | Archivo | Dónde se usa |
|---|---|---|
| Logo redondo Canella | `static/img/ic_launcher_round.webp` | Menú lateral y favicon (no el login: ver emblema abajo) |
| Logotipo "CANELLA" en blanco | `static/img/logo_canella_blanco.png` | Login: encima del orb del emblema |
| Fondo | `static/img/bk_index.jpg` | Login (capa clara al 35 %) y área de contenido del sistema (capa al 70 %) |
| Fuente de "ORBIT" | `static/vendor/oxanium-5.3.0/` (Oxanium 800, OFL) | Solo en el título del login |
| Estilos propios | `static/css/automate.css` | Todo el sistema |
| Emblema del login | `static/js/emblema-canella.js` (thinking-orbs, `static/vendor/thinking-orbs-0.3.2/`) + `.emblema` en el CSS | Login: orb de puntos (faja ondulante) dentro del disco de marca, con el logotipo encima. El disco está fijo; solo se mueven las partículas. Respaldo de la esfera 3D anterior: `static/js/emblema-esfera-3d.js` (no se carga) |
| Parallax del login | `static/js/parallax-acceso.js` | Login: fondo y frente siguen al mouse a distinto ritmo |
| Cerrar sesión | `.nav-cerrar-sesion` en el CSS | Ícono en rojo en el menú lateral |

Colores del título del login: degradado `#0b5e8a` → `#0e8f96` (versiones profundas del celeste
y aqua del fondo) para "ORBIT" y `#1a2831` (azul noche del logo) para "Canella". El emblema
usa el `#1a2831` de disco (sin sombra ni resplandor desde el 25/11/2026), puntos en el celeste
`#a4d1e4` del fondo y el logotipo en blanco encima.

Animaciones del login (todas se desactivan si el sistema tiene "reducir movimiento"; si el orb no
carga, el emblema queda como insignia plana: el fondo `#1a2831` de `.emblema` más el logotipo en
blanco, ya correctos en el HTML/CSS sin depender de JavaScript):

- **Emblema** (`emblema-canella.js` + `.emblema` en el CSS): el disco está quieto (no flota, no
  respira, sin sombra). Dentro,
  un orb de puntos de [thinking-orbs](https://github.com/Jakubantalik/thinking-orbs), variante
  `composing` (una faja de varias bandas que ondula alrededor de la esfera), dibujado en canvas 2D sin WebGL; densidad 1.4×
  porque la librería está afinada para 64 px y el emblema mide 120. El logotipo CANELLA va
  encima del orb. Con "reducir movimiento" el
  orb queda en un cuadro fijo.
- **Respiración** (`.fondo-capa` y `.fondo-imagen` en el CSS): el fondo se acerca y aleja con
  dos ritmos (24 s y 15 s, escala 1.03–1.12).
- **Parallax con el mouse** (`parallax-acceso.js`): el fondo se desplaza hasta 24 px en sentido
  contrario al cursor, con inercia; al salir de la ventana vuelve al centro.
- **El frente no se mueve** (emblema, título y formulario; desde el 25/11/2026): antes crecía y
  seguía al mouse, y movía el campo que la persona estaba por tocar. Solo el fondo da la
  profundidad. Solo con mouse (no en pantallas táctiles). Usa la propiedad `translate`, que se suma
  al `scale` de la respiración. Se desplaza la imagen dentro de su capa para no mostrar bordes.

Textos fijos:

- Nombre y subtítulo: `NOMBRE_PRODUCTO` y `SUBTITULO_PRODUCTO` en `app/__init__.py`. El título
  del login es la excepción: "ORBIT" (primera palabra del nombre) + "Automate", fijo en
  `base_publica.html`.
- Pie de página: `base.html`.
- Aviso de ayuda del login: `auth/acceso.html` (una línea, `.acceso-ayuda`: 14 px, más oscura y
  con un velo claro porque va sobre la ilustración del fondo).

Comportamiento del formulario de acceso (auditoría Krug del 25/11/2026):

- Al abrir, el cursor está en **Usuario**. Tras un intento fallido el usuario se conserva, la
  contraseña se borra y el cursor va directo a **Contraseña**.
- Campos vacíos: «Escribe tu usuario.» / «Escribe tu contraseña.» bajo cada campo.
- Botón del ojo para ver la contraseña: oculta por defecto y se vuelve a ocultar al enviar.


## Origen de los datos (SAP)

Los datos leídos de SAP Business One llevan el logo de SAP delante, con la macro
`origen_sap(detalle)` de `_macros.html` (imagen `static/img/SAP-Logo.svg.webp`, clase `.logo-sap`). El
tooltip dice qué se leyó. En un encabezado va **primero**, con `encabezado(..., origen=origen_sap(detalle, "grande"))`,
a la izquierda del título y del alto del título más el subtítulo. Así se usa en el visor de
Expedientes. Solo va donde el dato viene de SAP, no como adorno.


## Pantallas de administración: reglas de la auditoría Krug (23/11/2026)

- **Un módulo, un nombre.** Donde aparezca un módulo (menú, inicio, catálogo, Ejecuciones, Logs,
  detalle de una ejecución) se muestra su **nombre**; el identificador técnico (`corte_caja`)
  queda en el `title`, al pasar el mouse. El hub se llama «Hub». La traducción vive en un solo
  lugar: `_nombres_modulos()` en `app/core/admin.py`.
- **Una sola forma de fecha:** `DD/MM/AAAA HH:MM:SS` en todo el hub. En Logs se agregan los
  milisegundos atenuados, porque ordenan eventos del mismo segundo.
- **Los filtros piden lo que de verdad buscan.** El filtro «Usuario» de Logs busca el usuario STOD
  (parte del texto, sin distinguir mayúsculas), y así lo dice su texto de ayuda.
- **Sin referencias a archivos del código** (`docs/…`, `app/modulos/…`) en pantallas que usa
  Contabilidad: no los pueden abrir. Lo que haga falta explicar va en una línea; el detalle, donde
  se decide (p. ej. qué permite cada rol, en el formulario del usuario). Qué permite cada rol
  también aparece al pasar el mouse por su etiqueta.

Pruebas: `tests/test_logs_ejecuciones.py` (sección auditoría Krug) y
`tests/test_interfaz.py::test_administracion_no_remite_a_archivos_del_codigo`.


## Tablas: reglas de la plantilla del hub

Valen para toda tabla del hub (administración hoy; los módulos, cuando se revisen). Salen de la
auditoría Krug del 25/11/2026 de Inicio y Administración, vista a media pantalla (767 px).

| Regla | Cómo se aplica | Por qué |
|---|---|---|
| **La acción de cada fila nunca queda fuera de la vista** | Clase `col-acciones` en el `<th>` y el `<td>` de la columna de botones: queda fija a la derecha cuando la tabla se desplaza de lado (CSS en `automate.css`). El `<th>` lleva `<span class="visually-hidden">Acciones</span>` | En una ventana angosta «Editar» quedaba a la derecha, fuera de pantalla: la única acción de la fila se encontraba por accidente |
| **Lo que identifica la fila es lo que se pulsa** | Si la fila abre un detalle: `data-fila-enlace="<url>"` en el `<tr>` (toda la fila abre; Ctrl/clic central, en otra pestaña) **y** un `<a>` normal al mismo destino en la fila, en el dato que la identifica (el nombre de la persona). Los botones y enlaces de la fila siguen haciendo lo suyo | En Ejecuciones solo se podía pulsar un código (`7d905c14…`), lo menos significativo de la fila; en Usuarios, solo un botón al final |
| **Lo que falló se ve sin entrar** | En listas de ejecuciones, la línea del error bajo su estado (`.ejecucion-error`, texto completo al pasar el mouse) | Había que abrir cada ejecución para saber por qué falló |
| **Logs abre en lo útil** | Nivel mínimo **INFO** por defecto (`NIVEL_LOGS_POR_DEFECTO` en `app/core/admin.py`); el DEBUG sigue con «Todos» | Lo primero que se veía era el arranque del servidor y el registro de módulos |

Inicio, en la misma auditoría:

- Encabezado solo con el saludo («Hola, Ana»): el nombre del hub ya está en la marca del menú.
- El nombre del módulo en la tarjeta se escribe igual que en el menú (sin mayúsculas forzadas):
  regla «un módulo, un nombre».

Pruebas: `tests/test_interfaz.py` y `tests/test_logs_ejecuciones.py` (secciones «auditoría Krug
del 25/11/2026»).


## Navegación y modales: reglas de la plantilla del hub

Auditoría Krug y UI del 25/11/2026 sobre la navegación del hub y sus modales (menú, sesión y
confirmación).

| Regla | Cómo se aplica | Por qué |
|---|---|---|
| **«Volver» regresa a la lista como la dejaste** | Cada lista recuerda en la sesión su última dirección (filtros y página): `_recordar_lista()` y `url_volver()` en `app/core/admin.py`. «Volver», «Cancelar» y el pretítulo del detalle la usan. Solo acepta direcciones del propio hub y de esa lista | Al volver de una ejecución abierta desde «Error», la lista aparecía sin filtro y en la página 1 |
| **El pretítulo es la miga de pan** | En un detalle, el pretítulo (la lista de arriba) es un enlace: `encabezado(..., pretitulo_url=…)` | Parecía una ruta y no se podía pulsar |
| **Un objeto, un destino** | Una ejecución se abre siempre en su detalle, también desde Logs. Si ya no está registrada (las «sin cambios» antiguas se purgan), el detalle lleva a sus eventos en Logs con un aviso | Desde Ejecuciones iba al detalle y desde Logs a otra pantalla |
| **Los mensajes vacíos dicen la verdad** | El detalle de una ejecución busca eventos desde el día en que empezó (hasta la retención, `LOG_RETENCION_DIAS`) y, si no quedan, lo dice: «Ya no hay eventos de esta ejecución: los logs se conservan N días». Sin la columna «Ejecución», que ahí sería siempre la misma | Decía «No hay eventos con esos filtros» sin haber filtros, y solo buscaba en el último mes |
| **Al cerrar un modal, el foco vuelve a quien lo abrió** | `hub.confirmar` guarda el elemento enfocado al abrirse y lo enfoca al cerrarse (Esc, Cancelar o la X) | El foco caía al inicio de la página: quien usa teclado perdía su lugar |
| **El aviso que se descarta no vuelve** | «Entendido» del fin de jornada cierra el aviso hasta el final (ver «Expiración de la sesión») | Se volvía a abrir al segundo: no dejaba guardar |
| **Nombres cortados, completos al pasar el mouse** | `title` con el nombre del módulo en el menú | «Expedientes de Seguros (Tal…» no se podía leer completo |

Lo que ya cumplía y no se toca: el modal de confirmación empieza en «Cancelar», dice qué hace su
botón y se cierra con Esc o la X; el de sesión no se cierra con un clic fuera; el menú marca la
sección también en los detalles; las páginas de error tienen salida al inicio.

Pruebas: `tests/test_logs_ejecuciones.py` y `tests/test_interfaz.py` (secciones «navegación y
modales»). El cierre del aviso de jornada y la vuelta del foco son JavaScript: se verificaron en
el navegador simulando el reloj.
