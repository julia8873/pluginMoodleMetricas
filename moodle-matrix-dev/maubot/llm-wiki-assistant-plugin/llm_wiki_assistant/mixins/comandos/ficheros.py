from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any

import aiohttp
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

class FicherosMixin(ComandosBaseMixin):
# --8<-- [start:ficheros_handler]
    @command.new(name="ficheros", help="Lista los archivos .md/.txt encontrados en el repo de la BdC")
    async def ficheros_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !ficheros para listar los archivos del repositorio."""
        token = self._obtener_git_token()
        owner = self.config["default_owner"]
        repo = self.config["default_repo"]

        await evt.reply(f"Buscando archivos en {owner}/{repo}...")

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        async with aiohttp.ClientSession() as session:
            rutas = await self._listar_rutas(session, owner, repo, headers, "")

        if not rutas:
            await evt.reply("No se ha encontrado ningún archivo .md/.txt en la BdC.")
            return

        lista = "\n".join(f"- {r}" for r in sorted(rutas))
        await evt.reply(f"Archivos encontrados en {owner}/{repo}:\n{lista}")
# --8<-- [end:ficheros_handler]
