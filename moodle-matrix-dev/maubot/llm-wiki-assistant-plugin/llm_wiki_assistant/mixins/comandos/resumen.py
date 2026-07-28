from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.estudio import (
    generar_resumen_sesion
)
from llm_wiki_assistant.constants import SESION_VENTANA_SEGUNDOS

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

class ResumenMixin(ComandosBaseMixin):
# --8<-- [start:resumen_handler]
    @command.new(name="resumen", help="Resumen de lo que has repasado en esta sesión")
    async def resumen_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !resumen para generar un resumen de los apuntes."""
        desde = int(time.time()) - SESION_VENTANA_SEGUNDOS
        interacciones = await self.tracker.obtener_interacciones_recientes(evt.sender, desde)
        if not interacciones:
            horas = SESION_VENTANA_SEGUNDOS // 3600
            await evt.reply(f"No tienes actividad registrada en las últimas {horas} horas.")
            return

                contenido_docs = await self._obtener_documentacion(evt.sender,)

        try:
            resumen = await generar_resumen_sesion(interacciones, contenido_docs, self._crear_llm())
        except Exception as exc:
            await evt.reply(f"No he podido generar el resumen: {exc}")
            return

        await self._responder_con_latex(evt, resumen)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "resumen", "")
# --8<-- [end:resumen_handler]
