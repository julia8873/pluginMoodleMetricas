from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

import aiohttp
from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.constants import CONFIRMACION_BORRADO_TTL_SEGUNDOS

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

class BorrarMixin(ComandosBaseMixin):
# --8<-- [start:borrar_handler]
    @command.new(name="borrar", help="Borra un documento de la BdC (pide confirmación): !borrar <nombre>")
    @command.argument("nombre", pass_raw=True, required=True)
    async def borrar_handler(self, evt: MessageEvent, nombre: str) -> None:
        """Manejador del comando !borrar para eliminar un archivo."""
        nombre = nombre.strip()
        if not nombre:
            await evt.reply("Indica el nombre del documento a borrar: `!borrar <nombre>`.")
            return

        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        ruta = await self._resolver_ruta_unica(evt, nombre, owner, repo, headers)
        if ruta is None:
            return

        async with aiohttp.ClientSession() as session:
            info = await self._obtener_sha_y_contenido_github(session, owner, repo, headers, ruta)
        if info is None:
            await evt.reply(f"He encontrado `{ruta}` pero ya no existe en GitHub.")
            return

        clave = (evt.room_id, evt.sender)
        self.pendientes_borrado[clave] = {
            "ruta": ruta, "sha": info["sha"], "timestamp": int(time.time()),
        }
        await evt.reply(
            f"Vas a borrar «{ruta}» de la BdC permanentemente. "
            f"Escribe `confirmar` en los próximos {CONFIRMACION_BORRADO_TTL_SEGUNDOS // 60} minutos para continuar."
        )
# --8<-- [end:borrar_handler]

# --8<-- [start:procesar_confirmacion_borrado]
    async def _procesar_confirmacion_borrado(self, evt: MessageEvent, estado: dict) -> None:
        """Procesa la confirmación del usuario para borrar un archivo."""
        clave = (evt.room_id, evt.sender)
        self.pendientes_borrado.pop(clave, None)

        if int(time.time()) - estado["timestamp"] > CONFIRMACION_BORRADO_TTL_SEGUNDOS:
            await evt.reply("Han pasado más de 5 minutos, doy el borrado por cancelado.")
            return

        if evt.content.body.strip().lower() != "confirmar":
            await evt.reply("Borrado cancelado.")
            return

        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()
        branch = self.config["default_branch"] or "main"
        ruta = estado["ruta"]

        try:
            await self._borrar_archivo_github(
                owner, repo, token, ruta, branch, estado["sha"],
                mensaje_commit=f"Borrar '{ruta}' (por {evt.sender})",
            )
        except Exception as exc:
            self.log.warning(f"[llm_wiki_assistant] Error borrando '{ruta}' de GitHub: {exc}")
            await evt.reply(f"No he podido borrar «{ruta}»: {exc}")
            return

        await self.tracker.eliminar_fuentes_por_ruta(ruta)
        await evt.reply(f"«{ruta}» borrado de la BdC.")
        # T3: Registro en curaciones
        await self.tracker.log_curacion(evt.sender, evt.room_id, "borrado", ruta)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "documento_borrado", ruta)
# --8<-- [end:procesar_confirmacion_borrado]
