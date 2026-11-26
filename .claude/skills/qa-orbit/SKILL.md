---
name: qa-orbit
description: QA de ORBIT Canella (hub Flask de automatizaciones contables) combinando pytest, las reglas del hub y Playwright en un navegador real. Úsalo siempre que se pida revisar la calidad de un módulo, una pantalla o un cambio antes de subirlo a dev o pasarlo a main; «haz QA», «prueba esto», «revisa que funcione», «¿está listo para publicar?», «verifica el módulo X», «prueba en el navegador», «escribe pruebas de punta a punta/e2e/Playwright», «¿se rompió algo?», o al terminar un módulo nuevo, aunque no diga «QA». También para escribir o depurar pruebas en tests/e2e.
---

# QA de ORBIT Canella

QA aquí significa responder con evidencia una sola pregunta: **¿este cambio o módulo hace lo que
debe, sin romper nada del hub ni de los otros módulos, y lo puede usar una persona?** Se responde
en tres niveles, de lo más barato a lo más caro. Cada nivel atrapa cosas que los otros no ven, así
que en una revisión completa se hacen los tres; en un cambio chico, los que apliquen.

| Nivel | Qué atrapa | Cuánto tarda |
|---|---|---|
| 1. Pruebas automáticas (`python -m pytest`) | Reglas rotas, permisos, tareas, atomicidad, convivencia entre módulos | Segundos |
| 2. Revisión contra las reglas del hub | Pruebas que faltan, reglas que ninguna prueba puede verificar | Minutos |
| 3. Navegador real (Playwright) | JavaScript bajo la CSP, modales, spinners, mensajes, celular, errores de consola | Minutos |

## Seguridad: lo primero, siempre

ORBIT comparte la base `AUTOMATE_CANELLA` entre desarrollo y pruebas, y sus módulos hablan con
SAP, STOD, Exchange y carpetas con datos personales (DPI, expedientes). Un QA descuidado puede
escribir en producción o mandar un correo real a Cobros. Por eso:

- **Nunca** uses el servidor de `:5000`, `flask run` a secas ni `create_app()` sin `"testing"`:
  usan el `.env` real. Para todo lo que sea navegador usa el **servidor de QA**
  (`tests/e2e/servidor.py`): SQLite temporal, STOD simulado y **sin ninguna variable del `.env`**;
  si una pantalla intenta ir a SAP, verás «Faltan variables en .env», que es lo esperado.
- No corras tareas de módulos contra sistemas reales, no mandes correos y no apliques migraciones.
  Si para comprobar algo hace falta el sistema real, detente y dale al responsable los comandos.
- No copies a tu informe datos de `contexto/`, `instance/` ni `logs/`: tienen datos personales.

## Antes de empezar: delimita qué se revisa

1. ¿Qué cambió? `git status`, `git diff dev...HEAD --stat` o lo que diga el usuario. Si el
   usuario dice que cambió algo y Git no muestra nada en esa carpeta, **dilo al principio del
   informe**: quizá no guardó, está en otra rama u otro clon, y el QA estaría revisando lo viejo.
2. ¿Qué módulo o parte del núcleo toca? Lee su guía (tabla «Guías» del `README.md`) y, si es un
   módulo, su `__init__.py` (qué rutas, tareas y acciones tiene).
3. Si el cambio toca el núcleo (`app/core`, `base.html`, `static/js`), el alcance es **todo el
   hub**: revisa también pantallas de varios módulos, porque los afecta a todos.

## Nivel 1: pruebas automáticas

```bash
source .venv/Scripts/activate
python -m pytest                     # todo, ~30 s; debe terminar en "N passed"
python -m pytest --e2e tests/e2e     # navegador; requiere requirements-e2e.txt (ver más abajo)
```

Si algo falla, **entiende por qué antes de seguir**: una falla en `test_arquitectura.py` o en
`test_contrato_modulos.py` significa que el diseño rompió una regla del hub (un módulo que nombra
a otro, una ruta sin proteger); eso se corrige en el código, nunca en la prueba. Reporta la salida
exacta.

## Nivel 2: revisión contra las reglas del hub

Las reglas están en `docs/ARQUITECTURA.md` (principio 7, convivencia) y el juego mínimo de pruebas
en `docs/AGREGAR_MODULO.md` §9. Léelos: son la fuente de verdad y pueden haber cambiado. Para un
módulo, revisa como mínimo:

- **Cobertura del juego mínimo.** Recorre la tabla de §9 fila por fila y, para cada pieza que el
  módulo tenga (tareas, sistemas externos, acciones de administrador, modo simulación, consola,
  listados, archivos con datos personales), busca en `tests/test_<id>.py` la prueba que la cubre.
  Lo que no esté es un hallazgo, con el nombre de la prueba que falta.
- **Lo que ninguna prueba ve:** efectos externos (correo, archivos, SAP) al final de la tarea e
  idempotentes; ningún `db.session.commit()` dentro de una tarea; credenciales sin valor por
  defecto; variables nuevas documentadas en `.env.example`; mensajes al usuario en español y sin
  detalles técnicos; la guía del módulo actualizada con el cambio.
- **Migraciones:** si hay una nueva en `migrations/versions/`, que solo toque tablas del módulo
  (`<ID>_*`) y nunca proponga `drop_table` de otras.

## Nivel 3: navegador real con Playwright

Lee `references/playwright.md` antes de escribir código de Playwright: tiene la forma correcta de
esperar, ubicar elementos y depurar en este proyecto, y los errores que hacen pruebas frágiles.

**Preparación (una vez por equipo):**
```bash
pip install -r requirements-e2e.txt
python -m playwright install chromium
```

**a) Recorrido rápido con evidencia.** Para ver muchas pantallas de una vez con distintos usuarios:
```bash
python .claude/skills/qa-orbit/scripts/recorrido.py --salida <carpeta> --usuario qa_operador \
    "" m/<id>/ m/<id>/historial admin/usuarios
```
Rutas **sin barra inicial** (Git Bash las convierte en rutas de Windows). Usuarios:
`qa_super`, `qa_admin` (sin módulos), `qa_operador` (todos los módulos), `qa_sin_modulos`.
Deja `recorrido.md`, `recorrido.json` y capturas en escritorio y celular; sale con 1 si hubo 500,
errores de JavaScript o recursos que no cargaron. **Mira las capturas** (con la herramienta de
lectura de imágenes): el informe dice si la página cargó, no si se ve bien. Repite con
`qa_sin_modulos` para confirmar que ve el 403 en español, no un error.

Trampa conocida: en escritorio, una captura de **página completa** (`full_page=True`) pinta el
menú lateral fijo encima del contenido. No es un defecto de la pantalla; `recorrido.py` ya
captura el escritorio solo en lo visible. Si tomas capturas propias, haz lo mismo.

**Pantallas con datos.** El servidor de QA no tiene SAP, buzón ni carpetas, así que las bandejas
salen vacías con el aviso de «falta configuración». Para ver una pantalla con datos, reemplaza en
el proceso del servidor la fábrica del sistema externo por el doble que ya usan las pruebas del
módulo (`SapFalso`, `BuzonFalso`… en `tests/test_<id>.py`), con `monkeypatch` o asignando la
función antes de `ServidorQA(...).iniciar()`. Es el mismo contrato (`Protocol`), sin conexión real.

**b) Interacción.** Para lo que pasa al hacer clic (confirmaciones, spinners, formularios,
validaciones, aviso de sesión), escribe una prueba en `tests/e2e/` siguiendo
`tests/e2e/test_recorridos.py` (fixtures `servidor`, `servidor_aparte`, `errores_js`, helper
`entrar`). Si el recorrido es algo que se debe seguir cumpliendo, la prueba **se queda** en el
repositorio; si fue solo para explorar, bórrala al terminar.

**Qué mirar en cada pantalla** (`references/checklist-pantallas.md` tiene la lista completa):
textos en español y sin jerga técnica, error y estado vacío útiles, confirmación antes de toda
acción destructiva o hacia terceros, spinner en acciones lentas, nada se desborda en celular
(390 px), cero errores de consola.

## Informe

Entrega siempre este formato, en español, sin rodeos. El veredicto va primero porque es lo que el
usuario necesita para decidir si sube el cambio:

```markdown
# QA: <qué se revisó>

**Veredicto:** ✅ Listo para publicar | ⚠️ Publicable con pendientes | ❌ No publicar
<Una o dos frases: por qué.>

## Hallazgos
| # | Severidad | Hallazgo | Evidencia | Cómo reproducir |
|---|---|---|---|---|
| 1 | Alta | … | salida de pytest / captura / archivo:línea | pasos o comando |

## Qué se verificó
- Nivel 1: `python -m pytest` → N passed (y `--e2e` → N passed, si aplica)
- Nivel 2: filas del juego mínimo cubiertas / faltantes
- Nivel 3: pantallas recorridas, usuarios y anchos

## Qué NO se verificó y por qué
<Lo que requiere el sistema real (SAP, correo, carpetas) o una decisión del responsable.>
```

Severidad: **Alta** = pierde o expone datos, efecto hacia terceros indebido, permisos rotos o pantalla
que no funciona; **Media** = funciona mal o confunde a quien lo usa; **Baja** = detalle visual o de
texto. Un ❌ requiere al menos un hallazgo Alto. No inventes hallazgos para llenar la tabla: si no
hay, dilo. Guarda capturas y archivos de evidencia fuera del repositorio (carpeta temporal) salvo
que el usuario pida lo contrario.
