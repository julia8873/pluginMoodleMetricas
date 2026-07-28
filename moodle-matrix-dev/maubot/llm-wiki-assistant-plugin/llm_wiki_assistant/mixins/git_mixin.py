from __future__ import annotations
import asyncio
import base64
import time
from typing import TYPE_CHECKING, Optional, Any

import aiohttp
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.constants import AGENTS_MD_PATH

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

class GitMixin(_HostProtocol):
    def _obtener_git_token(self, cfg: Optional[dict] = None) -> str:
        """Obtiene el token adecuado según el proveedor (GitLab o GitHub)."""
        cfg = cfg or self.config
        prov = str(cfg.get("provider", "")).strip().lower()
        url = str(cfg.get("repo_url", "")).strip().lower()
        if prov == "gitlab" or "gitlab" in url:
            return cfg.get("gitlab_token", "") or cfg.get("github_token", "") or ""
        elif prov == "github" or "github.com" in url:
            return cfg.get("github_token", "") or cfg.get("gitlab_token", "") or ""
        return cfg.get("gitlab_token", "") or cfg.get("github_token", "") or ""

    async def _get_git_context(self, sender: str) -> tuple:
        """Devuelve (git_client, owner, repo, branch, token, raw_folder, bdc_cache_ttl_minutos)."""
        cfg = await self._config_para(sender)
        git = await self._git_para(sender)
        token = self._obtener_git_token(cfg)
        owner = cfg.get("default_owner", "")
        repo = cfg.get("default_repo", "")
        branch = cfg.get("default_branch", "main")
        raw_folder = cfg.get("raw_folder", "raw")
        ttl = cfg.get("bdc_cache_ttl_minutos", 30)
        return git, owner, repo, branch, token, raw_folder, ttl
# --8<-- [end:obtener_git_token]

    async def _obtener_documentacion(self, sender: str, filtro: str = "") -> str:
        """Obtiene la documentación o apuntes del repositorio Git."""
        git, owner, repo, _, token, _, ttl = await self._get_git_context(sender)
        ttl_segundos = ttl * 60
        async with aiohttp.ClientSession() as session:
            return await git.obtener_documentacion(
                session, owner, repo, token, filtro, self._cache_docs, ttl_segundos, self._semaforo_github, self.log
            )

    async def _recorrer_carpeta(self, session, sender: str, path: str, filtro: str = "") -> list:
        """Recorre una carpeta del repositorio y lista sus archivos."""
        git, owner, repo, _, token, _, _ = await self._get_git_context(sender)
        res = await git.obtener_documentacion(session, owner, repo, token, filtro, self._cache_docs, 0, self._semaforo_github, self.log)
        return [res] if res else []

# --8<-- [start:descargar_contenido_fichero]
    async def _descargar_contenido_fichero(self, session, path: str, download_url: str, headers: dict) -> str:
        """Descarga el contenido de un fichero específico del repositorio."""
        # Compatibilidad heredada
        return ""
# --8<-- [end:descargar_contenido_fichero]

    async def _listar_rutas(self, session, sender: str, path: str) -> list:
        """Lista las rutas disponibles en el repositorio."""
        git, owner, repo, _, token, _, ttl = await self._get_git_context(sender)
        ttl_segundos = ttl * 60
        return await git.listar_rutas(session, owner, repo, token, path, self._cache_rutas, ttl_segundos, self._semaforo_github)

    async def _listar_carpetas(self, sender: str) -> list:
        """Lista las carpetas disponibles en una ruta específica."""
        git, owner, repo, _, token, _, ttl = await self._get_git_context(sender)
        ttl_segundos = ttl * 60
        return await git.listar_carpetas(owner, repo, token, self._cache_carpetas, ttl_segundos, self._semaforo_github)

    async def _recorrer_carpeta_con_sha(self, session, sender: str, path: str) -> list:
        """Recorre una carpeta del repositorio incluyendo el hash SHA de los archivos."""
        git, owner, repo, _, token, _, _ = await self._get_git_context(sender)
        return await git.recorrer_carpeta_con_sha(session, owner, repo, token, path, self._semaforo_github)

    async def _obtener_sha_y_contenido_github(
        self, session, sender: str, path: str
    ) -> Optional[dict]:
        """Obtiene el SHA y el contenido de un archivo en GitHub."""
        git, owner, repo, _, token, _, _ = await self._get_git_context(sender)
        return await git.obtener_info_y_contenido(session, owner, repo, token, path, self._semaforo_github)

    async def _subir_o_actualizar_archivo_github(
        self, sender: str, path: str, contenido: str, mensaje_commit: str
    ) -> bool:
        """Sube un archivo nuevo o actualiza uno existente en GitHub."""
        git, owner, repo, branch, token, _, _ = await self._get_git_context(sender)
        return await git.subir_o_actualizar_archivo(owner, repo, token, path, contenido, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)

    async def _append_log_okf(
        self, sender: str, entrada: str, mensaje_commit: str
    ) -> None:
        """Añade un registro al log de operaciones del formato OKF."""
        git, owner, repo, branch, token, _, _ = await self._get_git_context(sender)
        await git.append_log_okf(owner, repo, token, branch, entrada, mensaje_commit, self._semaforo_github)
        self._invalidar_cache()

    async def _obtener_agents_md(self, sender: str) -> Optional[str]:
        """Obtiene el contenido del archivo de reglas AGENTS.md."""
        git, owner, repo, _, token, _, ttl = await self._get_git_context(sender)
        ttl_segundos = ttl * 60
        ahora = time.time()
        clave_cache = (owner, repo)

        if clave_cache in self._cache_agents_md:
            ts_guardado, contenido_cached = self._cache_agents_md[clave_cache]
            if ahora - ts_guardado < ttl_segundos:
                return contenido_cached

        async with aiohttp.ClientSession() as session:
            info = await git.obtener_info_y_contenido(session, owner, repo, token, AGENTS_MD_PATH, self._semaforo_github)
        if info is None:
            return None

        contenido = base64.b64decode(info["content"]).decode("utf-8") if info.get("content") else ""
        self._cache_agents_md[clave_cache] = (ahora, contenido)
        return contenido

    async def _borrar_archivo_github(
        self, sender: str, path: str, sha: str = "", mensaje_commit: str = ""
    ) -> None:
        """Elimina un archivo del repositorio de GitHub."""
        git, owner, repo, branch, token, _, _ = await self._get_git_context(sender)
        await git.borrar_archivo(owner, repo, token, path, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)

    async def _mover_archivo_github(
        self, sender: str, ruta_antigua: str, ruta_nueva: str
    ) -> None:
        """Mueve un archivo a una nueva ruta dentro del repositorio de GitHub."""
        git, owner, repo, branch, token, _, _ = await self._get_git_context(sender)
        await git.mover_archivo(owner, repo, token, ruta_antigua, ruta_nueva, branch, sender, self._semaforo_github, self._invalidar_cache)

    async def _subir_archivo_github(
        self, sender: str, path: str, contenido: str, mensaje_commit: str
    ) -> None:
        """Sube un archivo al repositorio de GitHub."""
        git, owner, repo, branch, token, _, _ = await self._get_git_context(sender)
        await git.subir_archivo(owner, repo, token, path, contenido, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)

    async def _resolver_ruta_unica(
        self, evt: MessageEvent, nombre: str
    ) -> Optional[str]:
        """Resuelve la ruta única para guardar un archivo en el repositorio."""
        async with aiohttp.ClientSession() as session:
            rutas = await self._listar_rutas(session, evt.sender, "")

        coincidencias = [r for r in rutas if nombre.lower() in r.lower()]

        if not coincidencias:
            await evt.reply(f"No he encontrado ningún documento que coincida con «{nombre}».")
            return None

        if len(coincidencias) > 1:
            lista = "\n".join(f"- {r}" for r in coincidencias)
            await evt.reply(f"Hay {len(coincidencias)} documentos que coinciden con «{nombre}»:\n{lista}\n\nRepite con un nombre más concreto.")
            return None

        return coincidencias[0]

    async def _guardar_ficheros_en_carpeta(self, evt: MessageEvent, ficheros: list, carpeta: Optional[str]) -> None:
        """Guarda múltiples archivos en una carpeta de destino."""
        _, _, _, _, _, raw_folder, _ = await self._get_git_context(evt.sender)
        carpeta_destino = carpeta or raw_folder

        for fichero in ficheros:
            marca_tiempo = int(time.time())
            nombre_base = fichero["nombre_archivo"].rsplit(".", 1)[0]
            ruta_repo = f"{carpeta_destino}/{nombre_base}-{marca_tiempo}.md"

            contenido_md = (
                f"# Fuente: {fichero['nombre_archivo']}\n\n"
                f"_Añadido por {evt.sender} el {marca_tiempo}._\n\n{fichero['texto_extraido']}"
            )

            try:
                await self._subir_archivo_github(
                    evt.sender, ruta_repo, contenido_md,
                    mensaje_commit=f"Añadir fuente '{fichero['nombre_archivo']}' (aportada por {evt.sender})",
                )
            except Exception as exc:
                self.log.warning(f"[llm_wiki_assistant] Error subiendo fuente a GitHub: {exc}")
                await evt.reply(f"No he podido subir «{fichero['nombre_archivo']}» al repositorio: {exc}")
                continue

            await evt.reply(f"«{fichero['nombre_archivo']}» añadido a la BdC en `{ruta_repo}`.")

            # Registro en curaciones, además de interacciones y fuentes_raw
            await self.tracker.log_curacion(evt.sender, evt.room_id, "subida", ruta_repo)
            await self.tracker.log_interaccion(evt.sender, evt.room_id, fichero["tipo_interaccion"], fichero["nombre_archivo"])
            await self.tracker.log_fuente_raw(evt.sender, evt.room_id, fichero["nombre_archivo"], ruta_repo)

            if self.config["ingest_automatico"]:
                await self._ejecutar_ingest_automatico(
                    evt, evt.sender, ruta_repo, fichero["nombre_archivo"],
                )

