from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker

if TYPE_CHECKING:
    class _HostProtocol:
        config: Any
        git: Any
        tracker: Tracker
        log: Any
        pendientes: dict
        lotes_subida: dict
        tareas_lote: dict
        pendientes_destino: dict
        pendientes_borrado: dict
        pendientes_borrado_carpeta: dict
        pendientes_ocr: dict
        _user_locks: dict
        _cache_docs: dict
        _cache_rutas: dict
        _cache_carpetas: dict
        _cache_agents_md: dict
        _semaforo_github: asyncio.Semaphore
        client: Any
        database: Any
else:
    _HostProtocol = object

from .base import ComandosBaseMixin

class EstadisticasMixin(ComandosBaseMixin):
# --8<-- [start:estadisticas_handler]
    @command.new(name="misestadisticas", help="Muestra tus métricas de trazabilidad en la BdC")
    async def estadisticas_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !estadisticas para mostrar estadísticas de estudio."""
        try:
            stats = await self.tracker.obtener_estadisticas(evt.sender)
        except Exception as exc:
            self.log.exception(f"[llm_wiki_assistant] Error consultando el tracker en !misestadisticas: {exc}")
            await evt.reply("He tenido un problema interno consultando tus estadísticas. Prueba en un momento.")
            return

        if stats["total_ejercicios"] > 0:
            porcentaje_acierto = round(100 * stats["ejercicios_correctos"] / stats["total_ejercicios"])
            linea_ejercicios = (
                f"- Ejercicios realizados: {stats['total_ejercicios']} "
                f"({stats['ejercicios_correctos']} correctos, {porcentaje_acierto}%)"
            )
        else:
            linea_ejercicios = "- Ejercicios realizados: 0"

        # T3: Incluir métricas de curación
        mensaje = (
            f"Estadísticas de {evt.sender}:\n"
            f"- Interacciones totales con el bot: {stats['total_interacciones']}\n"
            f"- Fuentes en bruto aportadas a la BdC: {stats['total_fuentes_raw']}\n"
            f"- Acciones de curación en la BdC: {stats['total_curaciones']} "
            f"(subidas: {stats['curaciones_subidas']}, movidos: {stats['curaciones_movidos']}, borrados: {stats['curaciones_borrados']})\n"
            f"{linea_ejercicios}"
        )
        await evt.reply(mensaje)
# --8<-- [end:estadisticas_handler]
