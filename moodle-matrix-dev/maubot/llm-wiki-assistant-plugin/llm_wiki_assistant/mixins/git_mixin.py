from __future__ import annotations
import asyncio
import base64
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

import aiohttp
from maubot.handlers import command, event
from maubot import MessageEvent
from mautrix.crypto.attachments import decrypt_attachment
from mautrix.errors import DecryptionError
from mautrix.types import EventType, MessageType

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.estudio import (
    EstudioError, buscar_ejercicios_por_tecnica, elegir_concepto, evaluar_respuesta,
    generar_ejercicio, generar_flashcard, generar_preguntas_para_conceptos, generar_resumen_sesion, listar_conceptos
)
from llm_wiki_assistant.image_ocr import OcrError, es_imagen_de_apuntes, transcribir_imagen, transcribir_pdf_escaneado
from llm_wiki_assistant.latex_render import procesar_texto_con_latex
from llm_wiki_assistant.llm_provider import LLMProvider
from llm_wiki_assistant.organizacion import VENTANA_LOTE_SEGUNDOS, es_respuesta_modo_lote, formatear_lista_carpetas, resolver_eleccion_carpeta, sanitizar_carpeta
from llm_wiki_assistant.pdf_ingest import PdfExtractionError, extraer_texto_pdf, parece_texto_de_baja_calidad
from llm_wiki_assistant.okf_ingest import IngestError, construir_prompt_ingest, construir_prompt_ingest_lote, dividir_en_lotes, parsear_respuesta_ingest
from llm_wiki_assistant.git_client import get_git_client
from llm_wiki_assistant.constants import AGENTS_MD_PATH

if TYPE_CHECKING:
    from maubot import Plugin
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
# --8<-- [start:obtener_git_token]
    def _obtener_git_token(self) -> str:
        """Obtiene el token adecuado según el proveedor (GitLab o GitHub)."""
        prov = str(self.config.get("provider", "")).strip().lower()
        url = str(self.config.get("repo_url", "")).strip().lower()
        if prov == "gitlab" or "gitlab" in url:
            return self.config.get("gitlab_token", "") or self.config.get("github_token", "") or ""
        elif prov == "github" or "github.com" in url:
            return self.config.get("github_token", "") or self.config.get("gitlab_token", "") or ""
        return self.config.get("gitlab_token", "") or self.config.get("github_token", "") or ""
# --8<-- [end:obtener_git_token]

# --8<-- [start:obtener_documentacion]
    async def _obtener_documentacion(self, owner: str, repo: str, token: str, filtro: str = "") -> str:
        """Obtiene la documentación o apuntes del repositorio Git."""
        ttl_segundos = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        async with aiohttp.ClientSession() as session:
            return await self.git.obtener_documentacion(
                session, owner, repo, token, filtro, self._cache_docs, ttl_segundos, self._semaforo_github, self.log
            )
# --8<-- [end:obtener_documentacion]

# --8<-- [start:recorrer_carpeta]
    async def _recorrer_carpeta(self, session, owner: str, repo: str, headers: dict, path: str, filtro: str = "") -> list:
        """Recorre una carpeta del repositorio y lista sus archivos."""
        # Mantener compatibilidad interna si se invoca directo
        token = headers.get("PRIVATE-TOKEN") or (headers.get("Authorization", "").replace("token ", "")) or self._obtener_git_token()
        res = await self.git.obtener_documentacion(session, owner, repo, token, filtro, self._cache_docs, 0, self._semaforo_github, self.log)
        return [res] if res else []
# --8<-- [end:recorrer_carpeta]

# --8<-- [start:descargar_contenido_fichero]
    async def _descargar_contenido_fichero(self, session, path: str, download_url: str, headers: dict) -> str:
        """Descarga el contenido de un fichero específico del repositorio."""
        # Compatibilidad heredada
        return ""
# --8<-- [end:descargar_contenido_fichero]

# --8<-- [start:listar_rutas]
    async def _listar_rutas(self, session, owner: str, repo: str, headers: dict, path: str) -> list:
        """Lista las rutas disponibles en el repositorio."""
        ttl_segundos = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        token = headers.get("PRIVATE-TOKEN") or (headers.get("Authorization", "").replace("token ", "")) or self._obtener_git_token()
        return await self.git.listar_rutas(session, owner, repo, token, path, self._cache_rutas, ttl_segundos, self._semaforo_github)
# --8<-- [end:listar_rutas]

# --8<-- [start:listar_carpetas]
    async def _listar_carpetas(self, owner: str, repo: str, token: str) -> list:
        """Lista las carpetas disponibles en una ruta específica."""
        ttl_segundos = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        return await self.git.listar_carpetas(owner, repo, token, self._cache_carpetas, ttl_segundos, self._semaforo_github)
# --8<-- [end:listar_carpetas]

# --8<-- [start:recorrer_carpeta_con_sha]
    async def _recorrer_carpeta_con_sha(self, session, owner: str, repo: str, headers: dict, path: str) -> list:
        """Recorre una carpeta del repositorio incluyendo el hash SHA de los archivos."""
        token = headers.get("PRIVATE-TOKEN") or (headers.get("Authorization", "").replace("token ", "")) or self._obtener_git_token()
        return await self.git.recorrer_carpeta_con_sha(session, owner, repo, token, path, self._semaforo_github)
# --8<-- [end:recorrer_carpeta_con_sha]

# --8<-- [start:obtener_sha_y_contenido_github]
    async def _obtener_sha_y_contenido_github(
        self, session, owner: str, repo: str, headers: dict, path: str
    ) -> Optional[dict]:
        """Obtiene el SHA y el contenido de un archivo en GitHub."""
        token = headers.get("PRIVATE-TOKEN") or (headers.get("Authorization", "").replace("token ", "")) or self._obtener_git_token()
        return await self.git.obtener_info_y_contenido(session, owner, repo, token, path, self._semaforo_github)
# --8<-- [end:obtener_sha_y_contenido_github]

# --8<-- [start:subir_o_actualizar_archivo_github]
    async def _subir_o_actualizar_archivo_github(
        self, owner: str, repo: str, token: str, path: str, contenido: str, branch: str, mensaje_commit: str
    ) -> bool:
        """Sube un archivo nuevo o actualiza uno existente en GitHub."""
        return await self.git.subir_o_actualizar_archivo(owner, repo, token, path, contenido, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)
# --8<-- [end:subir_o_actualizar_archivo_github]

# --8<-- [start:append_log_okf]
    async def _append_log_okf(
        self, owner: str, repo: str, token: str, branch: str, entrada: str, mensaje_commit: str
    ) -> None:
        """Añade un registro al log de operaciones del formato OKF."""
        await self.git.append_log_okf(owner, repo, token, branch, entrada, mensaje_commit, self._semaforo_github)
        self._invalidar_cache()
# --8<-- [end:append_log_okf]

# --8<-- [start:obtener_agents_md]
    async def _obtener_agents_md(self, owner: str, repo: str, token: str) -> Optional[str]:
        """Obtiene el contenido del archivo de reglas AGENTS.md."""
        ttl_segundos = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        ahora = time.time()
        clave_cache = (owner, repo)

        if clave_cache in self._cache_agents_md:
            ts_guardado, contenido_cached = self._cache_agents_md[clave_cache]
            if ahora - ts_guardado < ttl_segundos:
                return contenido_cached

        async with aiohttp.ClientSession() as session:
            info = await self.git.obtener_info_y_contenido(session, owner, repo, token, AGENTS_MD_PATH, self._semaforo_github)
        if info is None:
            return None

        contenido = base64.b64decode(info["content"]).decode("utf-8") if info.get("content") else ""
        self._cache_agents_md[clave_cache] = (ahora, contenido)
        return contenido
# --8<-- [end:obtener_agents_md]

# --8<-- [start:borrar_archivo_github]
    async def _borrar_archivo_github(
        self, owner: str, repo: str, token: str, path: str, branch: str, sha: str = "", mensaje_commit: str = ""
    ) -> None:
        """Elimina un archivo del repositorio de GitHub."""
        await self.git.borrar_archivo(owner, repo, token, path, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)
# --8<-- [end:borrar_archivo_github]

# --8<-- [start:mover_archivo_github]
    async def _mover_archivo_github(
        self, owner: str, repo: str, token: str, ruta_antigua: str, ruta_nueva: str, branch: str, sender: str
    ) -> None:
        """Mueve un archivo a una nueva ruta dentro del repositorio de GitHub."""
        await self.git.mover_archivo(owner, repo, token, ruta_antigua, ruta_nueva, branch, sender, self._semaforo_github, self._invalidar_cache)
# --8<-- [end:mover_archivo_github]

# --8<-- [start:subir_archivo_github]
    async def _subir_archivo_github(
        self, owner: str, repo: str, token: str, path: str, contenido: str, branch: str, mensaje_commit: str
    ) -> None:
        """Sube un archivo al repositorio de GitHub."""
        await self.git.subir_archivo(owner, repo, token, path, contenido, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)
# --8<-- [end:subir_archivo_github]

# --8<-- [start:resolver_ruta_unica]
    async def _resolver_ruta_unica(
        self, evt: MessageEvent, nombre: str, owner: str, repo: str, headers: dict
    ) -> Optional[str]:
        """Resuelve la ruta única para guardar un archivo en el repositorio."""
        async with aiohttp.ClientSession() as session:
            rutas = await self._listar_rutas(session, owner, repo, headers, "")

        coincidencias = [r for r in rutas if nombre.lower() in r.lower()]

        if not coincidencias:
            await evt.reply(f"No he encontrado ningún documento que coincida con «{nombre}».")
            return None

        if len(coincidencias) > 1:
            lista = "\n".join(f"- {r}" for r in coincidencias)
            await evt.reply(f"Hay {len(coincidencias)} documentos que coinciden con «{nombre}»:\n{lista}\n\nRepite con un nombre más concreto.")
            return None

        return coincidencias[0]
# --8<-- [end:resolver_ruta_unica]

# --8<-- [start:guardar_ficheros_en_carpeta]
    async def _guardar_ficheros_en_carpeta(self, evt: MessageEvent, ficheros: list, carpeta: Optional[str]) -> None:
        """Guarda múltiples archivos en una carpeta de destino."""
        token = self._obtener_git_token()
        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        branch = self.config["default_branch"] or "main"
        raw_folder = self.config["raw_folder"] or "raw"
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
                    owner, repo, token, ruta_repo, contenido_md, branch,
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
                    evt, owner, repo, token, branch, ruta_repo, fichero["nombre_archivo"],
                )
# --8<-- [end:guardar_ficheros_en_carpeta]

