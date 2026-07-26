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

class FeynmanMixin(ComandosBaseMixin):
# --8<-- [start:feynman_handler]
    @command.new(
        name="feynman",
        help="Técnica Feynman (explícamelo con tus palabras): !feynman [concepto] [tema:<...>] [tipo:<...>]",
    )
    @command.argument("nombre", pass_raw=True, required=False)
    async def feynman_handler(self, evt: MessageEvent, nombre: str = "") -> None:
        """Manejador del comando !feynman para practicar la Técnica de Feynman."""
        await self._plantear_pregunta_concepto(
            evt, tipo="feynman", nombre=nombre,
            plantilla_pregunta="Explícame con tus propias palabras qué es «{concepto}» (sin copiarlo de los apuntes).",
        )
# --8<-- [end:feynman_handler]
