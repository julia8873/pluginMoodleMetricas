# --8<-- [start:file_desc]
"""
Gestión automática del ciclo de vida de sesiones de estudio.

Este módulo arranca dos tareas asíncronas periódicas que se lanzan desde
bot.py::start() (loop asyncio del plugin, igual que ya usa asyncio.create_task
para los lotes de subida):

1. _detector_inactividad  — cada SESION_DETECTOR_INTERVALO_SEGUNDOS (10 min):
     · Busca sesiones abiertas sin actividad > SESION_INACTIVIDAD_SEGUNDOS (30 min).
     · Para cada una, obtiene sus interacciones, llama a generar_resumen_sesion()
       (la misma función que usa !resumen) y guarda el resultado con
       Tracker.guardar_resumen_sesion().
     · Cierra la sesión (Tracker.cerrar_sesion()).

2. _job_purga  — diariamente (86 400 s):
     · Llama a Tracker.purgar_datos_antiguos(retention_days) donde retention_days
       se lee de config['retention_days'] o de RETENTION_DAYS_DEFAULT.
     · Los resumenes_sesion NO se purgan: actúan como registro agregado de largo plazo.

Tanto !resumen (ventana fija, sin persistencia) como este módulo reutilizan
generar_resumen_sesion() de estudio.py; la diferencia es que aquí el resultado
se guarda en BD y la ventana es la sesión real, no una ventana de tiempo fija.
"""
# --8<-- [end:file_desc]

import asyncio
import logging

from .constants import (
    SESION_INACTIVIDAD_SEGUNDOS,
    SESION_DETECTOR_INTERVALO_SEGUNDOS,
    RETENTION_DAYS_DEFAULT,
)
from .estudio import generar_resumen_sesion

log = logging.getLogger("maubot.llm_wiki_assistant.sesiones")

PURGA_INTERVALO_SEGUNDOS = 86_400  # 24 horas


# --8<-- [start:arrancar_tareas]
def arrancar_tareas(bot) -> list:
    """
    Crea y lanza las tareas periódicas de gestión de sesiones y purga.
    Llamar desde bot.py::start() guardando las referencias devueltas para
    poder cancelarlas en stop() (si Maubot expone ese hook).

    bot: instancia de LlmWikiAssistant (tiene .tracker, .config, ._crear_llm(),
         ._obtener_documentacion(), .config[...]).
    """
    tareas = [
        asyncio.ensure_future(_detector_inactividad(bot)),
        asyncio.ensure_future(_job_purga(bot)),
    ]
    return tareas
# --8<-- [end:arrancar_tareas]


# --8<-- [start:detector_inactividad]
async def _detector_inactividad(bot) -> None:
    """
    Bucle periódico que cierra sesiones inactivas y genera su resumen.
    Corre indefinidamente; los errores puntuales se registran y el bucle continúa.
    """
    while True:
        await asyncio.sleep(SESION_DETECTOR_INTERVALO_SEGUNDOS)
        try:
            await _procesar_sesiones_inactivas(bot)
        except Exception:
            log.exception("[sesiones] Error en detector de inactividad")


async def _procesar_sesiones_inactivas(bot) -> None:
    """Lógica central del detector: busca, resume y cierra sesiones inactivas."""
    sesiones = await bot.tracker.obtener_sesiones_abiertas_inactivas(SESION_INACTIVIDAD_SEGUNDOS)
    if not sesiones:
        return

    log.info("[sesiones] %d sesión(es) inactiva(s) a cerrar", len(sesiones))

    llm = bot._crear_llm()

    for sesion in sesiones:
        session_id  = sesion["session_id"]
        student_id  = sesion["student_id"]
        room_id     = sesion["room_id"]
        try:
            interacciones = await bot.tracker.obtener_interacciones_sesion(session_id)
            
            # Obtener contexto documental para el fork específico del alumno
            try:
                contexto = await bot._obtener_documentacion(student_id) if interacciones else ""
            except Exception:
                log.exception(f"[sesiones] No se pudo obtener el contexto documental para {student_id}")
                contexto = ""

            if interacciones and contexto:
                resumen = await generar_resumen_sesion(interacciones, contexto, llm)
                await bot.tracker.guardar_resumen_sesion(session_id, resumen)
                log.info("[sesiones] Resumen guardado para sesión %s (%s)", session_id, student_id)
            await bot.tracker.cerrar_sesion(session_id)
            log.info("[sesiones] Sesión cerrada: %s | %s | %s", session_id, student_id, room_id)
        except Exception:
            log.exception("[sesiones] Error al cerrar sesión %s", session_id)
# --8<-- [end:detector_inactividad]


# --8<-- [start:job_purga]
async def _job_purga(bot) -> None:
    """
    Bucle diario de purga de datos personales antiguos.
    Respeta el plazo de retención configurado en base-config.yaml (retention_days).
    Los resumenes_sesion NO se purgan.

    ATENCIÓN LEGAL: Esta política de retención debe revisarse con el DPD de la UGR
    antes de poner en producción con alumnos reales (RGPD art. 5.1.e,
    LOPDGDD art. 34 — la UGR es universidad pública obligada a designar DPD).
    """
    while True:
        await asyncio.sleep(PURGA_INTERVALO_SEGUNDOS)
        try:
            retention_days = int(bot.config.get("retention_days", RETENTION_DAYS_DEFAULT))
            resultado = await bot.tracker.purgar_datos_antiguos(retention_days)
            log.info(
                "[sesiones] Purga completada — retention_days=%d, cutoff=%d",
                resultado["retention_days"], resultado["cutoff_timestamp"],
            )
        except Exception:
            log.exception("[sesiones] Error en job de purga")
# --8<-- [end:job_purga]
