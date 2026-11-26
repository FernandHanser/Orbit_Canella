# Qué mirar en cada pantalla de ORBIT

Lista para el nivel 3 (navegador). Cada punto dice **qué** comprobar y **por qué** importa en este
hub; el detalle de diseño está en `docs/INTERFAZ.md`.

## Funciona
- [ ] Responde 200 con el usuario que tiene el módulo; 403 con `qa_sin_modulos`, con la página de
      error en español (no un traceback ni una página en blanco).
- [ ] Cero errores de JavaScript y de CSP en la consola. Un script en línea rompe la CSP y deja
      botones muertos sin que nadie lo note.
- [ ] Ningún recurso (CSS, JS, imagen) responde 404.
- [ ] Los formularios envían con CSRF y, ante un dato inválido, muestran el error junto al campo y
      conservan lo que la persona escribió.

## Se entiende (Krug: «no me hagas pensar»)
- [ ] El título dice dónde estoy; el botón principal dice qué hace («Armar paquete», no «Enviar»).
- [ ] Textos en español, sin jerga técnica (`None`, `Traceback`, nombres de tablas, `KeyError`).
- [ ] Estado vacío útil: explica por qué no hay nada y qué hacer («No hay llamadas activas
      pendientes»), no una tabla vacía.
- [ ] Error útil: dice qué pasó y qué hacer, en palabras de la persona (p. ej. «Módulo sin conexión
      a SAP — Faltan variables en .env: …» para el administrador).
- [ ] Modo prueba o simulación visible cuando aplica (los correos no llegan a Cobros, etc.).

## Es seguro de usar
- [ ] Toda acción destructiva o con efectos hacia terceros (enviar correo, deshabilitar, borrar,
      escribir en SAP) pide confirmación con `data-confirmar`, y «Cancelar» no cambia nada.
- [ ] Las acciones lentas muestran spinner (`data-cargando`) y deshabilitan el botón: un doble clic
      no duplica el efecto.
- [ ] Las acciones de configuración solo aparecen (y solo funcionan) para administradores.
- [ ] No se muestran datos personales de más (DPI completo, rutas de red internas) a quien no los
      necesita.

## Se ve bien
- [ ] Escritorio (1366 px) y celular (390 px): nada se desborda en horizontal; las tablas largas
      se desplazan dentro de su contenedor.
- [ ] Listas largas paginadas; el número de consultas no crece con las filas (eso lo prueba
      `contar_consultas` en pytest).
- [ ] Coherente con el resto del hub: extiende `base.html`, usa las macros (`_macros.html`) y los
      componentes de Tabler, no estilos sueltos.
