from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
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

class PreguntaMixin(ComandosBaseMixin):
# --8<-- [start:pregunta_handler]
    @command.new(
        name="pregunta",
        help="Pregunta sobre la documentación del repo: !pregunta [tema:<carpeta/fichero>] <texto>",
    )
    @command.argument("texto", pass_raw=True, required=True)
    async def pregunta_handler(self, evt: MessageEvent, texto: str) -> None:
        """Manejador del comando !pregunta para resolver dudas sobre los apuntes."""
        token = self._obtener_git_token()
                texto, tema, _ = _extraer_modificadores(texto)
        if not texto:
            await evt.reply("Falta la pregunta. Formato: `!pregunta [tema:<carpeta/fichero>] <texto>`.")
            return

        await evt.reply("Buscando en la documentación, un momento...")

        clave = (evt.room_id, evt.sender)
        self.peticiones_llm[clave] = asyncio.current_task()
        try:
            contenido_docs = await self._obtener_documentacion(evt.sender, tema)
            if not contenido_docs and tema:
                await evt.reply(f"No he encontrado ningún fichero de la BdC que coincida con «{tema}».")
                return
            if not contenido_docs:
                await evt.reply("No he podido leer la documentación del repositorio.")
                return

            provider = self._crear_llm()
            respuesta = await provider.preguntar(texto, contenido_docs)
        except asyncio.CancelledError:
            self.log.info(f"Consulta LLM cancelada para {clave}")
            return
        except Exception as exc:
            await evt.reply(f"Error al consultar el modelo: {exc}")
            return
        finally:
            self.peticiones_llm.pop(clave, None)

        # T6: Usar LaTeX
        await self._responder_con_latex(evt, respuesta)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "pregunta", texto)
        await self.tracker.log_qa(evt.sender, evt.room_id, "pregunta", texto, respuesta, "informativo")
# --8<-- [end:pregunta_handler]
