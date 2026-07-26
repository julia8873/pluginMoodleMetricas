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

class AyudaMixin(ComandosBaseMixin):
# --8<-- [start:ayuda_handler]
    @command.new(name="ayuda", help="Lista todos los comandos disponibles")
    async def ayuda_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !ayuda para mostrar los comandos disponibles."""
        await evt.reply(self.AYUDA_TEXTO)
# --8<-- [end:ayuda_handler]
