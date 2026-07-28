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
        peticiones_llm: dict
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

class StopMixin(ComandosBaseMixin):
    @command.new(name="stop", help="Detiene procesos en curso y limpia tareas pendientes")
    async def stop_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !stop para detener la ejecución."""
        clave = (evt.room_id, evt.sender)
        
        canceladas = 0
        
        # 1. Cancelar consulta LLM actual si existe
        tarea_llm = self.peticiones_llm.pop(clave, None)
        if tarea_llm and not tarea_llm.done():
            tarea_llm.cancel()
            canceladas += 1
            
        # 2. Cancelar tareas en segundo plano (lotes)
        tarea = self.tareas_lote.pop(clave, None)
        if tarea and not tarea.done():
            tarea.cancel()
            canceladas += 1
            
        # 3. Limpiar diccionarios de pendientes
        if self.pendientes.pop(clave, None): canceladas += 1
        if self.pendientes_destino.pop(clave, None): canceladas += 1
        if self.pendientes_borrado.pop(clave, None): canceladas += 1
        if self.pendientes_borrado_carpeta.pop(clave, None): canceladas += 1
        if self.pendientes_ocr.pop(clave, None): canceladas += 1
        
        # Limpiar lotes_subida por si acaso
        if self.lotes_subida.pop(clave, None): canceladas += 1
        
        if canceladas > 0:
            await evt.reply("✅ Todas las operaciones en curso, subidas o confirmaciones pendientes han sido canceladas y detenidas.")
        else:
            await evt.reply("No tenías ninguna operación en curso ni confirmación pendiente que detener.")
