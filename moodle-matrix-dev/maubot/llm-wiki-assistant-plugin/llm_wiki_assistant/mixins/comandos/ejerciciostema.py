from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.estudio import (
    buscar_ejercicios_por_tecnica
)

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

class EjerciciosTemaMixin(ComandosBaseMixin):
# --8<-- [start:ejerciciostema_handler]
    @command.new(
        name="ejerciciostema",
        help="Busca ejercicios o problemas en la BdC que apliquen una técnica/teorema: !ejerciciostema <técnica>",
    )
    @command.argument("tecnica", pass_raw=True, required=True)
    async def ejerciciostema_handler(self, evt: MessageEvent, tecnica: str) -> None:
        """Manejador del comando !ejerciciostema para ejercicios de un tema."""
        tecnica = (tecnica or "").strip()
        if not tecnica:
            await evt.reply("Indica qué técnica, teorema o herramienta quieres buscar en los ejercicios de la BdC. Ejemplo: `!ejerciciostema integración por partes`")
            return

        await evt.reply(f"Buscando ejercicios en la BdC que apliquen «{tecnica}», un momento...")

                contenido_docs = await self._obtener_documentacion(evt.sender,)
        if not contenido_docs:
            await evt.reply("No he podido leer la documentación del repositorio.")
            return

        provider = self._crear_llm()
        try:
            ejercicios = await buscar_ejercicios_por_tecnica(tecnica, contenido_docs, provider)
        except Exception as exc:
            self.log.warning(f"[llm_wiki_assistant] Error buscando ejercicios por técnica: {exc}")
            await evt.reply(f"No he podido buscar los ejercicios: {exc}")
            return

        if not ejercicios:
            await evt.reply(f"No he encontrado en la BdC ningún ejercicio aplicable usando «{tecnica}».")
            return

        partes = [f"**Ejercicios encontrados sobre «{tecnica}» ({len(ejercicios)}):**\n"]
        for i, ej in enumerate(ejercicios, start=1):
            bloque = f"**{i}. [Fichero: `{ej['fichero']}`]**\n- **Enunciado:** {ej['enunciado']}"
            if ej['tecnica']:
                bloque += f"\n- **Cómo aplica:** {ej['tecnica']}"
            if ej['solucion']:
                bloque += f"\n- **Solución:** {ej['solucion']}"
            partes.append(bloque)

        texto_md = "\n\n".join(partes)
        await self._responder_con_latex(evt, texto_md)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "ejerciciostema", tecnica)
        await self.tracker.log_qa(evt.sender, evt.room_id, "ejerciciostema", tecnica, texto_md, "búsqueda de ejercicios")
    # --8<-- [end:ejerciciostema_handler]
