from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.estudio import (
    evaluar_respuesta,
    generar_ejercicio
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

class EjercicioMixin(ComandosBaseMixin):
# --8<-- [start:ejercicio_handler]
    @command.new(
        name="ejercicio",
        help="Repaso con ejercicios: !ejercicio [tema:<...>] [tipo:<...>] o !ejercicio <tu ejercicio/solución>",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def ejercicio_handler(self, evt: MessageEvent, texto: str = "") -> None:
        """Manejador del comando !ejercicio para generar ejercicios prácticos."""
        resto, tema, tipo_contenido = _extraer_modificadores(texto)
        if not resto:
            await self._plantear_pregunta(
                evt, tipo="ejercicio", generador=generar_ejercicio, tema=tema, tipo_contenido=tipo_contenido
            )
            return

                contenido_docs = await self._obtener_documentacion(evt.sender, tema)
        if not contenido_docs and tema:
            await evt.reply(f"No he encontrado ningún fichero de la BdC que coincida con «{tema}».")
            return
        if not contenido_docs:
            await evt.reply("No he podido leer la documentación del repositorio.")
            return

        try:
            resultado = await evaluar_respuesta(
                "ejercicio", "ejercicio propuesto por el estudiante",
                "El estudiante ha propuesto y/o resuelto un ejercicio por su cuenta.",
                resto, contenido_docs, self._crear_llm(),
            )
        except Exception as exc:
            await evt.reply(f"No he podido corregir la respuesta: {exc}")
            return

        emoji = "✅" if resultado["correcto"] else "❌"
        await self._responder_con_latex(evt, f"{emoji} {resultado['feedback']}")

        resultado_txt = "correcto" if resultado["correcto"] else "incorrecto"
        await self.tracker.log_ejercicio(evt.sender, evt.room_id, resultado_txt, tipo="ejercicio")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "ejercicio", resto)
# --8<-- [end:ejercicio_handler]
