from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.estudio import (
    generar_flashcard
)
from llm_wiki_assistant.helpers import _extraer_modificadores

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

class FlashcardMixin(ComandosBaseMixin):
# --8<-- [start:flashcard_handler]
    @command.new(
        name="flashcard",
        help="Pregunta de repaso sobre un concepto: !flashcard [tema:<...>] [tipo:<...>]",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def flashcard_handler(self, evt: MessageEvent, texto: str = "") -> None:
        """Manejador del comando !flashcard para practicar conceptos."""
        _, tema, tipo_contenido = _extraer_modificadores(texto)
        await self._plantear_pregunta(
            evt, tipo="flashcard", generador=generar_flashcard, tema=tema, tipo_contenido=tipo_contenido
        )
# --8<-- [end:flashcard_handler]
