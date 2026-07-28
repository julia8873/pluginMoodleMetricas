from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.organizacion import sanitizar_carpeta

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

class MoverMixin(ComandosBaseMixin):
# --8<-- [start:mover_handler]
    @command.new(name="mover", help="Mueve un documento de carpeta: !mover <nombre> -> <carpeta_destino|raiz>")
    @command.argument("texto", pass_raw=True, required=True)
    async def mover_handler(self, evt: MessageEvent, texto: str) -> None:
        """Manejador del comando !mover para cambiar la ubicación de un archivo."""
        if "->" not in texto:
            await evt.reply("Formato: `!mover <nombre_documento> -> <carpeta_destino|raiz>`")
            return

        nombre, _, destino_raw = texto.partition("->")
        nombre = nombre.strip()
        destino_raw = destino_raw.strip()
        if not nombre or not destino_raw:
            await evt.reply("Faltan el nombre del documento o la carpeta destino.")
            return

        carpeta_destino = "" if destino_raw.lower() in ("raiz", "raíz", "0", "-") else sanitizar_carpeta(destino_raw)
        if destino_raw.lower() not in ("raiz", "raíz", "0", "-") and not carpeta_destino:
            await evt.reply(f"«{destino_raw}» no es una carpeta válida.")
            return

                branch = self.config["default_branch"] or "main"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        ruta_antigua = await self._resolver_ruta_unica(evt, nombre)
        if ruta_antigua is None:
            return

        nombre_fichero = ruta_antigua.rsplit("/", 1)[-1]
        ruta_nueva = f"{carpeta_destino}/{nombre_fichero}" if carpeta_destino else nombre_fichero

        if ruta_nueva == ruta_antigua:
            await evt.reply(f"«{ruta_antigua}» ya está en esa carpeta.")
            return

        try:
            await self._mover_archivo_github(evt.sender, ruta_antigua, ruta_nueva)
        except Exception as exc:
            self.log.warning(f"[llm_wiki_assistant] Error moviendo '{ruta_antigua}' -> '{ruta_nueva}': {exc}")
            await evt.reply(f"No he podido mover «{ruta_antigua}»: {exc}")
            return

        await self.tracker.actualizar_ruta_fuente(ruta_antigua, ruta_nueva)
        await evt.reply(f"«{ruta_antigua}» movido a `{ruta_nueva}`.")
        # T3: Registro en curaciones
        await self.tracker.log_curacion(evt.sender, evt.room_id, "movido", f"{ruta_antigua} -> {ruta_nueva}")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "documento_movido", f"{ruta_antigua} -> {ruta_nueva}")
# --8<-- [end:mover_handler]
