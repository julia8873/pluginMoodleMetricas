from __future__ import annotations
import asyncio
import base64
from datetime import datetime
from typing import TYPE_CHECKING, Any

import aiohttp
from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.okf_ingest import IngestError, construir_prompt_ingest, construir_prompt_ingest_lote, dividir_en_lotes, parsear_respuesta_ingest
from llm_wiki_assistant.constants import AGENTS_MD_PATH, OKF_LOG_PATH
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

class IngestMixin(_HostProtocol):
# --8<-- [start:ejecutar_ingest_automatico]
    async def _ejecutar_ingest_automatico(
        self, evt: MessageEvent, ruta_fuente_repo: str, nombre_archivo: str,
    ) -> None:
        try:
            agents_md = await self._obtener_agents_md(evt.sender)
            if not agents_md:
                await evt.reply(
                    f"«{nombre_archivo}» está guardado en `{ruta_fuente_repo}`, pero no he "
                    f"encontrado `{AGENTS_MD_PATH}` en el repo, así que no puedo estructurarlo "
                    "automáticamente en okf/. Revísalo cuando puedas."
                )
                return

            await evt.reply(f"Estructurando «{nombre_archivo}» en la BdC (okf/), un momento...")

            async with aiohttp.ClientSession() as session:
                info_fuente = await self._obtener_sha_y_contenido_github(session, evt.sender, ruta_fuente_repo)
            if info_fuente is None:
                raise RuntimeError(f"No he podido releer «{ruta_fuente_repo}» recién subido.")
            contenido_fuente = base64.b64decode(info_fuente["content"]).decode("utf-8")
            if len(contenido_fuente.splitlines()) > 350:
                await self._ejecutar_ingest_por_lotes(evt, ruta_fuente_repo, nombre_archivo, contenido_fuente, agents_md)
                return

            timestamp_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            instruccion = construir_prompt_ingest(agents_md, ruta_fuente_repo, nombre_archivo, timestamp_iso)

            llm = self._crear_llm()
            respuesta = await llm.generar_texto(instruccion, contenido_fuente)
            resultado = parsear_respuesta_ingest(respuesta)

        except IngestError as exc:
            self.log.warning(f"[llm_wiki_assistant] Respuesta de INGEST inválida para '{ruta_fuente_repo}': {exc}")
            await evt.reply(
                f"«{nombre_archivo}» está guardado en `{ruta_fuente_repo}`, pero no he podido "
                f"estructurarlo automáticamente en okf/ ({exc}). Queda pendiente de curar a mano."
            )
            return
        except Exception as exc:
            self.log.warning(f"[llm_wiki_assistant] Error en ingesta automática de '{ruta_fuente_repo}': {exc}")
            await evt.reply(
                f"«{nombre_archivo}» está guardado en `{ruta_fuente_repo}`, pero ha fallado la "
                f"estructuración automática en okf/ ({exc}). Queda pendiente de curar a mano."
            )
            return

        creados, actualizados = [], []
        for fichero in resultado["ficheros"]:
            try:
                fue_actualizacion = await self._subir_o_actualizar_archivo_github(evt.sender, fichero["path"], fichero["contenido"],
                    mensaje_commit=f"INGEST automático de '{ruta_fuente_repo}' (por {evt.sender})",
                )
            except Exception as exc:
                self.log.warning(f"[llm_wiki_assistant] Error subiendo '{fichero['path']}' de la ingesta: {exc}")
                await evt.reply(f"No he podido guardar `{fichero['path']}`: {exc}")
                continue
            (actualizados if fue_actualizacion else creados).append(fichero["path"])

        if resultado["log_entry"]:
            try:
                await self._append_log_okf(evt.sender, resultado["log_entry"],
                    mensaje_commit=f"Log de INGEST automático de '{ruta_fuente_repo}'",
                )
            except Exception as exc:
                self.log.warning(f"[llm_wiki_assistant] Error haciendo append a {OKF_LOG_PATH}: {exc}")

        await self.tracker.log_curacion(evt.sender, evt.room_id, "ingest_automatico", ruta_fuente_repo)

        partes = [f"He estructurado «{nombre_archivo}» en la BdC."]
        if creados:
            partes.append("**Ficheros nuevos:**\n" + "\n".join(f"- `{p}`" for p in creados))
        if actualizados:
            partes.append("**Ficheros actualizados:**\n" + "\n".join(f"- `{p}`" for p in actualizados))
        if resultado["contradicciones"]:
            partes.append("**Contradicciones detectadas:**\n" + "\n".join(f"- {c}" for c in resultado["contradicciones"]))
        if resultado["preguntas_seguimiento"]:
            partes.append("**Preguntas de seguimiento:**\n" + "\n".join(f"- {p}" for p in resultado["preguntas_seguimiento"]))

        await evt.reply("\n\n".join(partes))
# --8<-- [end:ejecutar_ingest_automatico]

# --8<-- [start:ejecutar_ingest_por_lotes]
    async def _ejecutar_ingest_por_lotes(
        self, evt: MessageEvent, ruta_fuente_repo: str, nombre_archivo: str, contenido_fuente: str, agents_md: str
    ) -> None:
        """Ejecuta el proceso de ingesta de archivos en lotes."""
        lotes = dividir_en_lotes(contenido_fuente, max_lineas=120, solapamiento=20)
        total_lotes = len(lotes)
        await evt.reply(f"El documento «{nombre_archivo}» es extenso ({len(contenido_fuente.splitlines())} líneas). Iniciando extracción exhaustiva por {total_lotes} lotes en okf/...")

        llm = self._crear_llm()
        timestamp_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        creados_totales, actualizados_totales = [], []

        for i, texto_lote in enumerate(lotes, start=1):
            await evt.reply(f"Procesando lote {i}/{total_lotes} de «{nombre_archivo}»...")
            instruccion = construir_prompt_ingest_lote(
                agents_md, ruta_fuente_repo, nombre_archivo, timestamp_iso, i, total_lotes
            )
            try:
                respuesta = await llm.generar_texto(instruccion, texto_lote)
                resultado = parsear_respuesta_ingest(respuesta)
            except Exception as exc:
                self.log.warning(f"[llm_wiki_assistant] Error procesando lote {i}/{total_lotes} de '{ruta_fuente_repo}': {exc}")
                await evt.reply(f"Lote {i}/{total_lotes}: Hubo un problema extrayendo conceptos ({exc}). Continuando con el siguiente lote...")
                continue

            for fichero in resultado["ficheros"]:
                try:
                    fue_actualizacion = await self._subir_o_actualizar_archivo_github(evt.sender, fichero["path"], fichero["contenido"],
                        mensaje_commit=f"INGEST lote {i}/{total_lotes} de '{ruta_fuente_repo}' (por {evt.sender})",
                    )
                    (actualizados_totales if fue_actualizacion else creados_totales).append(fichero["path"])
                except Exception as exc:
                    self.log.warning(f"[llm_wiki_assistant] Error subiendo '{fichero['path']}' en lote {i}: {exc}")

            if resultado.get("log_entry"):
                try:
                    await self._append_log_okf(evt.sender, resultado["log_entry"],
                        mensaje_commit=f"Log INGEST lote {i}/{total_lotes} de '{ruta_fuente_repo}'",
                    )
                except Exception as exc:
                    self.log.warning(f"[llm_wiki_assistant] Error append log okf lote {i}: {exc}")

        await self.tracker.log_curacion(evt.sender, evt.room_id, "ingest_lotes", ruta_fuente_repo)
        resumen_partes = [f"Ingesta por lotes completada al 100% para «{nombre_archivo}» ({total_lotes} lotes procesados)."]
        if creados_totales:
            resumen_partes.append(f"**Ficheros nuevos ({len(creados_totales)}):**\n" + "\n".join(f"- `{p}`" for p in sorted(set(creados_totales))[:20]))
        if actualizados_totales:
            resumen_partes.append(f"**Ficheros actualizados ({len(actualizados_totales)}):**\n" + "\n".join(f"- `{p}`" for p in sorted(set(actualizados_totales))[:20]))
        await evt.reply("\n\n".join(resumen_partes))
# --8<-- [end:ejecutar_ingest_por_lotes]

# --8<-- [start:ingest_lotes_handler]
    @command.new(
        name="ingest_lotes",
        help="Extrae el 100% de conceptos por lotes de un fichero largo de raw/: !ingest_lotes [tema:<...>]",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def ingest_lotes_handler(self, evt: MessageEvent, texto: str = "") -> None:
        """Comando para iniciar manualmente la ingesta por lotes."""

        _, tema, _ = _extraer_modificadores(texto)
        if not tema:
            await evt.reply("Indica la ruta del fichero de raw/ a ingestar. Ejemplo: `!ingest_lotes [tema:raw/00Libro de Teoria Musical - Nestor Crespo-1784644777.md]`.")
            return

        if not tema.startswith("raw/"):
            tema = f"raw/{tema}" if not tema.endswith(".md") else f"raw/{tema}"

        await evt.reply(f"Leyendo `{tema}` del repositorio para ingesta por lotes...")
        async with aiohttp.ClientSession() as session:
            info_fuente = await self._obtener_sha_y_contenido_github(session, evt.sender, tema)
        if not info_fuente:
            await evt.reply(f"No he encontrado o no he podido leer `{tema}` en el repositorio.")
            return

        contenido_fuente = base64.b64decode(info_fuente["content"]).decode("utf-8")
        agents_md = await self._obtener_agents_md(evt.sender)
        if not agents_md:
            await evt.reply("No he encontrado AGENTS.md en el repositorio para guiar la ingesta.")
            return

        nombre_archivo = tema.split("/")[-1]
        await self._ejecutar_ingest_por_lotes(evt, tema, nombre_archivo, contenido_fuente, agents_md)
# --8<-- [end:ingest_lotes_handler]

