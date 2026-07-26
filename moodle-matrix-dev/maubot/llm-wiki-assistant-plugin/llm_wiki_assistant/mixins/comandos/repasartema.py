from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.estudio import (
    generar_preguntas_para_conceptos, listar_conceptos
)
from llm_wiki_assistant.constants import MAX_CONCEPTOS_REPASO_TEMA
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

class RepasarTemaMixin(ComandosBaseMixin):
# --8<-- [start:repasartema_handler]
    @command.new(
        name="repasartema",
        help="Repasa TODOS los conceptos de un tema, uno a uno: !repasartema [tema:<...>] [tipo:<...>]",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def repasartema_handler(self, evt: MessageEvent, texto: str = "") -> None:
        """Manejador del comando !repasartema para estudiar un tema completo."""
        _, tema, tipo_contenido = _extraer_modificadores(texto)

        owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
        contenido_docs = await self._obtener_documentacion(owner, repo, token, tema)
        if not contenido_docs and tema:
            await evt.reply(f"No he encontrado ningún fichero de la BdC que coincida con «{tema}».")
            return
        if not contenido_docs:
            await evt.reply("No he podido leer la documentación del repositorio.")
            return

        llm = self._crear_llm()
        try:
            conceptos = await listar_conceptos(contenido_docs, llm, tipo_contenido)
        except Exception as exc:
            self.log.warning(f"[llm_wiki_assistant] Error listando conceptos en !repasartema: {exc}")
            await evt.reply(f"No he podido extraer los conceptos del tema: {exc}")
            return

        if not conceptos:
            await evt.reply("No he encontrado conceptos con esos filtros en la BdC.")
            return

        truncado = len(conceptos) > MAX_CONCEPTOS_REPASO_TEMA
        if truncado:
            conceptos = conceptos[:MAX_CONCEPTOS_REPASO_TEMA]

        try:
            preguntas = await generar_preguntas_para_conceptos(conceptos, contenido_docs, llm, tipo_contenido)
        except Exception as exc:
            self.log.warning(f"[llm_wiki_assistant] Error generando lote de preguntas: {exc}")
            await evt.reply(f"No he podido generar las preguntas del tema: {exc}")
            return

        primera, *resto = preguntas
        total = len(preguntas)
        self.pendientes[(evt.room_id, evt.sender)] = {
            "tipo": "repaso_tema",
            "concepto": primera["concepto"],
            "pregunta": primera["pregunta"],
            "timestamp": int(time.time()),
            "cola": resto,
            "contenido_docs": contenido_docs,
            "avanzado": 1,
            "total": total,
            "correctos": 0,
        }

        aviso_truncado = f" (Máximo {MAX_CONCEPTOS_REPASO_TEMA} conceptos.)" if truncado else ""
        texto_md = (
            f"Vamos a repasar {total} conceptos, uno a uno.{aviso_truncado}\n\n"
            f"**(1/{total}) {primera['concepto']}**\n\n{primera['pregunta']}"
        )
        await self._responder_con_latex(evt, texto_md)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "repaso_tema", f"sesión iniciada: {total} conceptos")
# --8<-- [end:repasartema_handler]
