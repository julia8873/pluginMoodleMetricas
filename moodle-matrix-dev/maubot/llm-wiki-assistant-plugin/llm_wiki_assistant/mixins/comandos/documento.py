from __future__ import annotations
import asyncio
import base64
from datetime import datetime
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

class DocumentoMixin(ComandosBaseMixin):
# --8<-- [start:documento_handler]
    @command.new(name="documento", help="Información de un documento concreto: !documento <nombre>")
    @command.argument("nombre", pass_raw=True, required=True)
    async def documento_handler(self, evt: MessageEvent, nombre: str) -> None:
        """Manejador del comando !documento para obtener información de un archivo."""
        nombre = nombre.strip()
        if not nombre:
            await evt.reply("Indica el nombre del documento: `!documento <nombre>`.")
            return

        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        try:
            coincidencias_db = await self.tracker.buscar_fuentes_por_nombre(nombre)
        except Exception as exc:
            self.log.exception(f"[llm_wiki_assistant] Error consultando el tracker en !documento: {exc}")
            await evt.reply("Error interno consultando la base de datos.")
            return

        async with aiohttp.ClientSession() as session:
            rutas_repo = await self._listar_rutas(session, owner, repo, headers, "")

        rutas_db = {c["ruta_repo"] for c in coincidencias_db}
        rutas_solo_repo = [r for r in rutas_repo if nombre.lower() in r.lower() and r not in rutas_db]

        total = len(coincidencias_db) + len(rutas_solo_repo)
        if total == 0:
            await evt.reply(f"No he encontrado ningún documento que coincida con «{nombre}».")
            return
        if total > 1:
            lineas = [f"- {c['ruta_repo']}" for c in coincidencias_db] + [f"- {r}" for r in rutas_solo_repo]
            await evt.reply(f"Hay {total} documentos que coinciden:\n" + "\n".join(lineas) + "\n\nRepite con un nombre más concreto.")
            return

        info_db = coincidencias_db[0] if coincidencias_db else None
        ruta = info_db["ruta_repo"] if info_db else rutas_solo_repo[0]

        async with aiohttp.ClientSession() as session:
            datos = await self.git.obtener_info_y_contenido(session, owner, repo, token, ruta, self._semaforo_github)
            if not datos:
                await evt.reply(f"He encontrado `{ruta}` pero no he podido leer su contenido.")
                return

        contenido_decodificado = ""
        if datos.get("content"):
            try:
                contenido_decodificado = base64.b64decode(datos["content"]).decode("utf-8", errors="replace")
            except Exception:
                contenido_decodificado = ""

        vista_previa = contenido_decodificado.strip()
        if len(vista_previa) > 300:
            vista_previa = vista_previa[:300] + "..."

        tamano_kb = round((datos.get("size") or 0) / 1024, 1)
        partes = [f"**{ruta}**", f"Tamaño: {tamano_kb} KB"]

        if info_db:
            fecha = datetime.fromtimestamp(info_db["timestamp"]).strftime("%d/%m/%Y %H:%M")
            partes.append(f"Aportado por: {info_db['student_id']} el {fecha}")
        else:
            async with aiohttp.ClientSession() as session:
                historial = await self.git.obtener_historial_fichero(session, owner, repo, token, ruta, self._semaforo_github)
                if historial:
                    commit = historial[0]
                    partes.append(f"Última modificación: {commit['author_date']} (commit de {commit['author_name']})")

        if vista_previa:
            partes.append(f"\nVista previa:\n{vista_previa}")

        await evt.reply("\n".join(partes))
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "documento", ruta)
# --8<-- [end:documento_handler]
