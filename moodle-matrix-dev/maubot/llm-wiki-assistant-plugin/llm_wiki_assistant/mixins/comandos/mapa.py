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

class MapaMixin(ComandosBaseMixin):
# --8<-- [start:mapa_handler]
    @command.new(name="mapa", help="Qué conceptos dominas y cuáles tienes que repasar")
    async def mapa_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !mapa para generar un mapa conceptual."""
        conceptos = await self.tracker.obtener_mapa_conceptos(evt.sender)
        if not conceptos:
            await evt.reply("Todavía no tienes conceptos registrados. Prueba con !concepto, !flashcard o !feynman.")
            return

        dominados = [c for c in conceptos if c["dominado"]]
        en_progreso = [c for c in conceptos if not c["dominado"]]

        partes = []
        if dominados:
            lineas = "\n".join(f"- {c['concepto']} ({c['aciertos']}/{c['intentos']})" for c in dominados)
            partes.append(f"**Dominados:**\n{lineas}")
        if en_progreso:
            lineas = "\n".join(f"- {c['concepto']} ({c['aciertos']}/{c['intentos']})" for c in en_progreso)
            partes.append(f"**Por repasar:**\n{lineas}")

        await self._responder_con_latex(evt, "\n\n".join(partes))
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "mapa", "")
# --8<-- [end:mapa_handler]
