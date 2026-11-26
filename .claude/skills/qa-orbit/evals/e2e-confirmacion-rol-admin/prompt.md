---
tags: [qa-orbit]
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Necesito una prueba de punta a punta con Playwright: en Administración > Usuarios y permisos, al editar a una persona y marcarle el rol de Administrador, debe salir la confirmación «¿Dar el rol de Administrador?»; si cancelo, no se guarda nada. Escríbela, córrela y dime si pasa.
