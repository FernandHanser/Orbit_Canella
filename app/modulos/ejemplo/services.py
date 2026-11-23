"""Lógica del módulo de ejemplo. No depende de Flask: recibe el contexto de ejecución."""
from app.core.ejecuciones import ContextoEjecucion


def tarea_demo(ctx: ContextoEjecucion) -> dict:
    """Simula un proceso por pasos. Con el parámetro ``fallar=1`` termina en error
    para demostrar el registro de trazas."""
    pasos = int(ctx.parametros.get("pasos", 3))
    ctx.log.info("Preparando %s pasos de demostración", pasos, extra={"evento": "demo.preparacion"})
    for numero in range(1, pasos + 1):
        ctx.log.debug("Paso %s de %s completado", numero, pasos, extra={"evento": "demo.paso"})
    if str(ctx.parametros.get("fallar", "")).lower() in {"1", "true", "si", "sí"}:
        raise RuntimeError("Error simulado solicitado por el usuario (demostración).")
    if pasos == 0:
        ctx.estado = "advertencia"
        ctx.log.warning("No se ejecutó ningún paso", extra={"evento": "demo.sin_pasos"})
    return {"pasos_completados": pasos, "nota": "Resultado de demostración, sin datos reales."}
