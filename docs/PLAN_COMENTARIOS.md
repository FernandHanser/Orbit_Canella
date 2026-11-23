# Plan: comentarios que explican el porqué, no el cómo

Pendiente para la noche del 29/09/2026 (o la siguiente sesión). Nace de la auditoría de
arquitectura de esa misma fecha (ver [ARQUITECTURA.md](ARQUITECTURA.md#auditoría-de-arquitectura-29092026)).
Regla base: **expresar la intención en el código; comentar solo lo que el código no puede decir
por sí mismo** (decisiones, trade-offs, advertencias, TODO con dueño). Nunca el cómo, nunca
código comentado, nunca fecha o autoría (para eso está git).

## Diagnóstico (ya hecho, 29/09/2026)

Escaneo automatizado sobre `app/` antes de tocar nada:

| Categoría prohibida | Resultado |
|---|---|
| `TODO`/`FIXME`/`XXX` | 0 |
| Comentarios con fecha o autoría (`// Modificado por…`, fechas sueltas) | 0 |
| Código comentado (líneas de código desactivadas) | 0 (1 falso positivo: era una nota del porqué) |
| Comentarios obvios (`i++; // incrementa i`) | 0 en el muestreo por patrón |
| Divisores de sección (`# ------ nombre`) | 29 archivos los usan, **todos rotulados** (no son ruido tipo `//////////`) |

Conclusión: no hace falta una reescritura masiva. Lo que un grep no encuentra —comentarios que
explican un cómo complicado en vez de que el código se simplifique— requiere lectura dirigida.

## Fase 1 — Fijar la política por escrito

- [ ] Crear `docs/ESTILO_COMENTARIOS.md`: las reglas de arriba, con un ejemplo real del repo de
      un comentario bueno (explica un trade-off) y uno malo corregido (explicaba el cómo; se
      simplificó el código y el comentario sobró).

## Fase 2 — Blindarlo con una prueba

- [ ] `tests/test_comentarios.py`, con AST sobre `app/` igual que `test_arquitectura.py`: falla si
      aparece `TODO`/`FIXME` sin referencia a un pendiente conocido, código comentado, o un
      comentario con fecha/autoría. Sin esto, el problema vuelve a aparecer en unos meses.

## Fase 3 — Revisión manual dirigida (el trabajo real)

Por archivo: comentario que solo repite la línea siguiente → se borra. Comentario que explica un
cómo complicado → se simplifica el código (mejor nombre, función extraída) y el comentario
sobra solo. Orden, del más comentado al menos:

- [ ] `app/modulos/expedientes_seguros/` (`servicios.py`, `static/visor.js`, `reglas.py`)
- [ ] `app/modulos/corte_caja/` (`servicios.py`, `buzon.py`)
- [ ] `app/core/` (`auth.py`, `sesion.py`, `ejecuciones.py`, `logs.py`)
- [ ] JS compartido (`static/js/interaccion.js`, `static/js/sesion.js`)

## Fase 4 — Decisión pendiente: los divisores de sección rotulados

29 archivos usan `# ------ nombre` para navegar archivos largos (`servicios.py`, `admin.py`). No
mienten ni envejecen, así que no violan la regla del porqué — pero tampoco dejan que la
estructura del código hable sola. Dos caminos, falta decidir cuál:

- [ ] **Dejarlos** (son un mapa, no una explicación del cómo), o
- [ ] **Quitarlos**, dividiendo esos archivos por sección (p. ej. `servicios.py` →
      `servicios_bandeja.py`, `servicios_correo.py`): más trabajo, más limpio a largo plazo.

## Orden sugerido al retomarlo

1. Fase 1 y 2 primero (dejan la política escrita **y** exigible).
2. Fase 4 (la decisión) antes de la Fase 3, para no revisar dos veces los mismos archivos si al
   final se dividen.
3. Fase 3 al final, módulo por módulo.
