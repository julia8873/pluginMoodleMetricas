# --8<-- [start:file_desc]
"""
Plugin de maubot para asistencia de estudio universitario con GitHub y Matrix.

Módulo principal: define la clase GithubBot, la gestión de comandos de Matrix,
la organización de ficheros en carpetas de GitHub, y la coordinación de las
herramientas de estudio (flashcards, ejercicios, técnica Feynman, repaso de
temas, extracción de ejercicios por técnica y curación de base de conocimiento).
"""

import asyncio
import base64
import re
import time
from datetime import datetime
from typing import Optional, Type

import aiohttp

from maubot import Plugin, MessageEvent
from maubot.handlers import command, event
from mautrix.crypto.attachments import decrypt_attachment
from mautrix.errors import DecryptionError
from mautrix.types import EventType, MessageType
from mautrix.util.async_db import UpgradeTable
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

from .db import Tracker, upgrade_table
from .estudio import (
    EstudioError,
    buscar_ejercicios_por_tecnica,
    elegir_concepto,
    evaluar_respuesta,
    generar_ejercicio,
    generar_flashcard,
    generar_preguntas_para_conceptos,
    generar_resumen_sesion,
    listar_conceptos,
)
from .image_ocr import OcrError, es_imagen_de_apuntes, transcribir_imagen, transcribir_pdf_escaneado
from .latex_render import procesar_texto_con_latex
from .llm_provider import LLMProvider
from .organizacion import (
    VENTANA_LOTE_SEGUNDOS,
    es_respuesta_modo_lote,
    formatear_lista_carpetas,
    resolver_eleccion_carpeta,
    sanitizar_carpeta,
)
from .pdf_ingest import PdfExtractionError, extraer_texto_pdf, parece_texto_de_baja_calidad
from .okf_ingest import (
    IngestError,
    construir_prompt_ingest,
    construir_prompt_ingest_lote,
    dividir_en_lotes,
    parsear_respuesta_ingest,
)
from .git_client import get_git_client


# --------------------------------------------------------------------
# Constantes de configuración
# --------------------------------------------------------------------

# Tiempo máximo que se espera la respuesta a una flashcard/ejercicio/concepto/feynman
# pendiente antes de dejar de interpretar el siguiente mensaje del estudiante como tal.
PENDIENTE_TTL_SEGUNDOS = 30 * 60

# Tiempo máximo para confirmar un !borrar antes de darlo por cancelado.
CONFIRMACION_BORRADO_TTL_SEGUNDOS = 5 * 60

# Ventana de tiempo que cuenta como "sesión actual" para el comando !resumen.
SESION_VENTANA_SEGUNDOS = 3 * 60 * 60

# Tope de conceptos que se preguntan en una sola sesión de !repasartema.
MAX_CONCEPTOS_REPASO_TEMA = 25

# Semáforo de concurrencia máxima para peticiones a GitHub (recorrido de carpetas).
MAX_CONCURRENCIA_GITHUB = 5

# Ficheros de metadatos/esquema OKF que nunca deben entrar en el contexto de
# estudio: son instrucciones para el LLM-editor de la wiki (AGENTS.md), índice
# de navegación (index.md) o historial append-only que solo crece (log.md).
# No aportan contenido de estudio y solo restan espacio de contexto al LLM.
# Se excluyen únicamente al construir la documentación para flashcards/ejercicios/
# etc. (_recorrer_carpeta); NO afecta a listar/gestionar ficheros (_listar_rutas),
# donde el usuario sigue pudiendo ver, mover o borrar estos ficheros a mano.
FICHEROS_EXCLUIDOS_CONTEXTO = {"agents.md", "index.md", "log.md"}

# Rutas fijas del bundle OKF v0.1 (ver README/AGENTS.md de la BdC). No son
# configurables porque forman parte del propio estándar OKF, no de la
# organización particular de un repo.
AGENTS_MD_PATH = "AGENTS.md"
OKF_LOG_PATH = "okf/log.md"

# Reconoce "nombre: <nuevo nombre>" o "renombrar <nuevo nombre>" en diálogos de destino.
PATRON_RENOMBRAR = re.compile(r"^(?:nombre|renombrar)\s*:?\s+(.+)$", re.IGNORECASE)

# Modificadores opcionales tema:<...> y tipo:<...> en comandos de estudio.
PATRON_TEMA = re.compile(r"\btema:(\S+)", re.IGNORECASE)
PATRON_TIPO = re.compile(r"\btipo:(\S+)", re.IGNORECASE)


def _extraer_modificadores(texto: str) -> tuple:
    """
    Busca 'tema:<...>' y 'tipo:<...>' en el argumento de un comando y los separa del
    resto del texto (nombre de concepto, enunciado, pregunta...).
    Devuelve (resto, tema, tipo_contenido).
    """
    tema = ""
    tipo_contenido = ""

    m = PATRON_TEMA.search(texto)
    if m:
        tema = m.group(1)
        texto = texto[: m.start()] + texto[m.end():]

    m = PATRON_TIPO.search(texto)
    if m:
        tipo_contenido = m.group(1).lower()
        texto = texto[: m.start()] + texto[m.end():]

    return texto.strip(), tema, tipo_contenido


# --------------------------------------------------------------------
# Configuración del plugin
# --------------------------------------------------------------------

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("provider")         # Proveedor Git principal ('gitlab' o 'github')
        helper.copy("repo_url")         # URL completa de tu repositorio Git
        helper.copy("gitlab_url")       # URL base del servidor GitLab
        helper.copy("gitlab_token")     # Token de acceso de GitLab
        helper.copy("github_token")     # Token de acceso personal de GitHub
        helper.copy("default_owner")    # Owner/organización del repo por defecto
        helper.copy("default_repo")     # Nombre del repo por defecto
        helper.copy("default_branch")   # Rama del repo donde se sube el material
        helper.copy("raw_folder")       # Carpeta del repo para subidas en bruto
        helper.copy("llm_base_url")     # URL base del backend LLM
        helper.copy("llm_api_key")      # API key del backend LLM
        helper.copy("llm_model")        # Modelo LLM para texto y herramientas de estudio
        helper.copy("llm_vision_model") # Modelo LLM para visión (imágenes y PDFs escaneados)
        helper.copy("llm_vision_base_url") # URL base opcional para el backend de visión
        helper.copy("llm_vision_api_key")  # API key opcional para el backend de visión
        helper.copy("bdc_cache_ttl_minutos") # TTL en minutos para la caché en memoria de la BdC
        helper.copy("ingest_automatico")     # Si True, estructura automáticamente cada fuente subida en okf/


# --------------------------------------------------------------------
# Clase principal GithubBot
# --------------------------------------------------------------------

class GithubBot(Plugin):
# --8<-- [end:file_desc]

    async def start(self) -> None:
        self.config.load_and_update()
        self.git = get_git_client(self.config)
        self.tracker = Tracker(self.database)
        self.pendientes = {}
        self.lotes_subida = {}
        self.tareas_lote = {}
        self.pendientes_destino = {}
        self.pendientes_borrado = {}
        self.pendientes_borrado_carpeta = {}
        # Confirmacion de si el usuario quiere OCR visual tras ver la vista previa del PDF
        self.pendientes_ocr = {}

        # T2: Control de concurrencia por usuario/sala para evitar race conditions
        self._user_locks = {}

        # T4: Cachés en memoria con TTL configurable
        self._cache_docs = {}      # (owner, repo, filtro) -> (timestamp, contenido)
        self._cache_rutas = {}     # (owner, repo, path) -> (timestamp, lista_rutas)
        self._cache_carpetas = {}  # (owner, repo) -> (timestamp, lista_carpetas)
        self._cache_agents_md = {} # (owner, repo) -> (timestamp, contenido_agents_md)
        self._semaforo_github = asyncio.Semaphore(MAX_CONCURRENCIA_GITHUB)

    def _obtener_git_token(self) -> str:
        """Obtiene el token adecuado según el proveedor (GitLab o GitHub)."""
        prov = str(self.config.get("provider", "")).strip().lower()
        url = str(self.config.get("repo_url", "")).strip().lower()
        if prov == "gitlab" or "gitlab" in url:
            return self.config.get("gitlab_token", "") or self.config.get("github_token", "") or ""
        elif prov == "github" or "github.com" in url:
            return self.config.get("github_token", "") or self.config.get("gitlab_token", "") or ""
        return self.config.get("gitlab_token", "") or self.config.get("github_token", "") or ""

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @classmethod
    def get_db_upgrade_table(cls) -> Optional[UpgradeTable]:
        return upgrade_table

    def _get_user_lock(self, room_id: str, sender: str) -> asyncio.Lock:
        """Obtiene o crea el cerrojo de concurrencia para el estudiante en la sala."""
        clave = (room_id, sender)
        if clave not in self._user_locks:
            self._user_locks[clave] = asyncio.Lock()
        return self._user_locks[clave]

    def _invalidar_cache(self) -> None:
        """Invalida toda la caché en memoria tras operaciones de escritura en GitHub."""
        self._cache_docs.clear()
        self._cache_rutas.clear()
        self._cache_carpetas.clear()
        self._cache_agents_md.clear()
        self.log.info("[github_bot] Caché en memoria de la BdC invalidada.")

    def _crear_llm(self) -> LLMProvider:
        return LLMProvider(self.config["llm_base_url"], self.config["llm_api_key"], self.config["llm_model"])

    def _crear_llm_vision(self) -> LLMProvider:
        base_url = self.config["llm_vision_base_url"] or self.config["llm_base_url"]
        api_key = self.config["llm_vision_api_key"] or self.config["llm_api_key"]
        modelo_vision = self.config["llm_vision_model"] or self.config["llm_model"]
        return LLMProvider(base_url, api_key, modelo_vision)

    # --------------------------------------------------------------------
    # T6: Renderizado y envío con LaTeX a imágenes PNG
    # --------------------------------------------------------------------

    async def _responder_con_latex(self, evt: MessageEvent, texto_md: str) -> None:
        """
        Envia una respuesta por Matrix procesando previamente cualquier fórmula LaTeX
        para renderizarla como imagen PNG ad-hoc en un mensaje HTML.
        """
        async def _subir_png(png_bytes: bytes, alt_text: str) -> Optional[str]:
            try:
                uri = await self.client.upload_media(png_bytes, mime_type="image/png", filename="formula.png")
                return uri
            except Exception as exc:
                self.log.warning(f"[github_bot] Error subiendo fórmula LaTeX renderizada: {exc}")
                return None

        body_plano, html_formatted = await procesar_texto_con_latex(texto_md, _subir_png)

        # Si no se sustituyó ninguna fórmula ni hay HTML especial, enviar reply normal.
        if html_formatted == body_plano or "<img" not in html_formatted:
            await evt.reply(body_plano)
        else:
            content = {
                "msgtype": "m.text",
                "body": body_plano,
                "format": "org.matrix.custom.html",
                "formatted_body": html_formatted,
            }
            await evt.respond(content)

    # --------------------------------------------------------------------
    # T4: Descarga y caché del árbol y contenido de GitHub
    # --------------------------------------------------------------------

    async def _obtener_documentacion(self, owner: str, repo: str, token: str, filtro: str = "") -> str:
        ttl_segundos = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        async with aiohttp.ClientSession() as session:
            return await self.git.obtener_documentacion(
                session, owner, repo, token, filtro, self._cache_docs, ttl_segundos, self._semaforo_github, self.log
            )

    async def _recorrer_carpeta(self, session, owner: str, repo: str, headers: dict, path: str, filtro: str = "") -> list:
        # Mantener compatibilidad interna si se invoca directo
        token = headers.get("PRIVATE-TOKEN") or (headers.get("Authorization", "").replace("token ", "")) or self._obtener_git_token()
        res = await self.git.obtener_documentacion(session, owner, repo, token, filtro, self._cache_docs, 0, self._semaforo_github, self.log)
        return [res] if res else []

    async def _descargar_contenido_fichero(self, session, path: str, download_url: str, headers: dict) -> str:
        # Compatibilidad heredada
        return ""

    async def _listar_rutas(self, session, owner: str, repo: str, headers: dict, path: str) -> list:
        ttl_segundos = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        token = headers.get("PRIVATE-TOKEN") or (headers.get("Authorization", "").replace("token ", "")) or self._obtener_git_token()
        return await self.git.listar_rutas(session, owner, repo, token, path, self._cache_rutas, ttl_segundos, self._semaforo_github)

    async def _listar_carpetas(self, owner: str, repo: str, token: str) -> list:
        ttl_segundos = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        return await self.git.listar_carpetas(owner, repo, token, self._cache_carpetas, ttl_segundos, self._semaforo_github)

    async def _recorrer_carpetas_dirs(self, session, owner: str, repo: str, headers: dict, path: str, acumulador: list) -> None:
        pass

    async def _recorrer_carpeta_con_sha(self, session, owner: str, repo: str, headers: dict, path: str) -> list:
        token = headers.get("PRIVATE-TOKEN") or (headers.get("Authorization", "").replace("token ", "")) or self._obtener_git_token()
        return await self.git.recorrer_carpeta_con_sha(session, owner, repo, token, path, self._semaforo_github)

    # --------------------------------------------------------------------
    # Ingesta de fuentes (PDFs, imágenes y apuntes manuscritos)
    # --------------------------------------------------------------------

    @event.on(EventType.ROOM_MESSAGE)
    async def on_message(self, evt: MessageEvent) -> None:
        if evt.sender == self.client.mxid:
            return

        clave = (evt.room_id, evt.sender)
        lock = self._get_user_lock(evt.room_id, evt.sender)

        # T2: Protegemos la evaluación del mensaje y acceso al estado con lock
        async with lock:
            if evt.content.msgtype == MessageType.TEXT and evt.content.body and not evt.content.body.startswith("!"):
                # Confirmacion OCR: tiene prioridad sobre todo lo demas
                ocr_pendiente = self.pendientes_ocr.pop(clave, None)
                if ocr_pendiente is not None:
                    await self._procesar_confirmacion_ocr(evt, ocr_pendiente)
                    return

                borrado_pendiente = self.pendientes_borrado.get(clave)
                if borrado_pendiente is not None:
                    await self._procesar_confirmacion_borrado(evt, borrado_pendiente)
                    return

                borrado_carpeta_pendiente = self.pendientes_borrado_carpeta.get(clave)
                if borrado_carpeta_pendiente is not None:
                    await self._procesar_confirmacion_borrado_carpeta(evt, borrado_carpeta_pendiente)
                    return

                destino_pendiente = self.pendientes_destino.get(clave)
                if destino_pendiente is not None:
                    await self._procesar_respuesta_destino(evt, destino_pendiente)
                    return

                pendiente = self.pendientes.pop(clave, None)
                if pendiente is not None:
                    if int(time.time()) - pendiente["timestamp"] > PENDIENTE_TTL_SEGUNDOS:
                        await evt.reply("Han pasado más de 30 minutos, doy la pregunta anterior por caducada.")
                    else:
                        await self._evaluar_pendiente(evt, pendiente)
                    return

            nombre_archivo = evt.content.body or ""
            es_fichero_pdf = evt.content.msgtype == MessageType.FILE and nombre_archivo.lower().endswith(".pdf")
            es_foto_apuntes = (
                evt.content.msgtype == MessageType.IMAGE
                or (evt.content.msgtype == MessageType.FILE and es_imagen_de_apuntes(nombre_archivo))
            )

            if not es_fichero_pdf and not es_foto_apuntes:
                return

            if not nombre_archivo:
                nombre_archivo = "apuntes.jpg" if es_foto_apuntes else "documento.pdf"

            await evt.reply(f"Leyendo «{nombre_archivo}», un momento...")

            try:
                contenido_binario = await self._descargar_adjunto(evt)
            except DecryptionError as exc:
                self.log.warning(f"[github_bot] Error descifrando adjunto: {exc}")
                await evt.reply("He descargado el fichero pero no he podido descifrarlo. ¿Puedes reenviarlo?")
                return
            except Exception as exc:
                self.log.warning(f"[github_bot] Error descargando adjunto: {exc}")
                await evt.reply("No he podido descargar el fichero. ¿Puedes reenviarlo?")
                return

            llm_vision = self._crear_llm_vision()
            tipo_interaccion = "pdf_subido"

            if es_foto_apuntes:
                mime_type = getattr(getattr(evt.content, "info", None), "mimetype", None) or "image/jpeg"
                await evt.reply("Es una imagen: transcribiendo los apuntes manuscritos con el modelo, puede tardar unos segundos...")
                try:
                    texto_extraido = await transcribir_imagen(contenido_binario, mime_type, llm_vision)
                except (OcrError, Exception) as exc:
                    self.log.error(f"[github_bot] Error al transcribir imagen «{nombre_archivo}»: {exc}")
                    await evt.reply(
                        f"⚠️ Error al transcribir «{nombre_archivo}»: {exc}\n\n"
                        "Verifica la clave API/configuración del LLM en base-config.yaml o intenta de nuevo."
                    )
                    return
                tipo_interaccion = "apuntes_manuscritos_foto"
            else:
                try:
                    texto_extraido = extraer_texto_pdf(contenido_binario)
                    texto_de_baja_calidad = parece_texto_de_baja_calidad(texto_extraido)
                except PdfExtractionError:
                    texto_extraido = ""
                    texto_de_baja_calidad = True

                vista_previa = self._vista_previa_transcripcion(texto_extraido, 400) if texto_extraido else ""

                if texto_de_baja_calidad:
                    aviso = (
                        f"He detectado que «{nombre_archivo}» contiene notacion musical, "
                        "simbolos de partitura u otro contenido que no se lee bien como texto.\n\n"
                    )
                else:
                    aviso = f"He extraido texto de «{nombre_archivo}». Vista previa:\n\n> {vista_previa}\n\n"

                await evt.reply(
                    aviso +
                    "¿Quieres que use **OCR visual** (Gemini lee cada pagina como imagen, "
                    "mas lento pero mucho mas preciso para partituras, libros escaneados y "
                    "documentos con graficos)?\n\n"
                    "Responde **si** para OCR o **no** para guardar el texto extraido tal como esta."
                )
                self.pendientes_ocr[clave] = {
                    "nombre_archivo": nombre_archivo,
                    "contenido_binario": contenido_binario,
                    "texto_extraido": texto_extraido,
                    "llm_vision": llm_vision,
                    "timestamp": int(time.time()),
                }
                return

            # Solo llega aqui el camino de imagenes (es_foto_apuntes=True),
            # ya que el camino PDF hace return despues de guardar pendientes_ocr.
            await self._encolar_para_lote(evt, nombre_archivo, texto_extraido, tipo_interaccion)

    async def _procesar_confirmacion_ocr(self, evt: MessageEvent, estado: dict) -> None:
        """
        Procesa la respuesta del usuario a la pregunta de si quiere OCR visual.
        Si responde 'si'/'s'/'yes'/'y' -> lanza transcripcion visual pagina a pagina.
        Cualquier otra respuesta -> usa el texto extraido previamente con pypdf.
        """
        respuesta = (evt.content.body or "").strip().lower()
        nombre_archivo = estado["nombre_archivo"]
        contenido_binario = estado["contenido_binario"]
        llm_vision = estado["llm_vision"]
        texto_extraido = estado["texto_extraido"]

        if respuesta in ("si", "sí", "s", "yes", "y", "1"):
            await evt.reply(
                f"Usando OCR visual para «{nombre_archivo}»... "
                "Gemini leerá cada página como imagen. Esto puede tardar varios minutos si el PDF es largo."
            )
            try:
                async def notificar_progreso(pag_actual: int, total_pags: int) -> None:
                    await evt.reply(f"⏳ Procesando OCR visual... (página {pag_actual}/{total_pags})")

                texto_extraido, paginas_fallidas = await transcribir_pdf_escaneado(
                    contenido_binario, llm_vision, progress_callback=notificar_progreso
                )
                if paginas_fallidas:
                    self.log.warning(f"[github_bot] Páginas con error al transcribir PDF: {paginas_fallidas}")
                    await evt.reply(f"⚠️ Aviso: Hubo problemas al transcribir {len(paginas_fallidas)} página(s).")
                tipo_interaccion = "pdf_escaneado_ocr"
            except (OcrError, Exception) as exc:
                self.log.error(f"[github_bot] Error en OCR visual de «{nombre_archivo}»: {exc}")
                await evt.reply(
                    f"⚠️ Error al procesar «{nombre_archivo}» con OCR visual: {exc}\n\n"
                    "Si el error persiste, verifica la clave API/configuración del LLM en base-config.yaml o responde **no** al subir el archivo para guardar el texto extraído sin OCR visual."
                )
                return
        else:
            await evt.reply(f"De acuerdo, usaré el texto extraido directamente para «{nombre_archivo}».")
            tipo_interaccion = "pdf_subido"

        await self._encolar_para_lote(evt, nombre_archivo, texto_extraido, tipo_interaccion)


    async def _encolar_para_lote(
        self, evt: MessageEvent, nombre_archivo: str, texto_extraido: str, tipo_interaccion: str
    ) -> None:
        clave = (evt.room_id, evt.sender)
        self.lotes_subida.setdefault(clave, []).append({
            "nombre_archivo": nombre_archivo,
            "texto_extraido": texto_extraido,
            "tipo_interaccion": tipo_interaccion,
        })

        tarea_anterior = self.tareas_lote.get(clave)
        if tarea_anterior is not None and not tarea_anterior.done():
            tarea_anterior.cancel()

        self.tareas_lote[clave] = asyncio.create_task(self._debounce_lote(evt.room_id, evt.sender))

    @staticmethod
    def _vista_previa_transcripcion(texto: str, longitud: int = 350) -> str:
        vista = (texto or "").strip()
        if len(vista) > longitud:
            vista = vista[:longitud] + "..."
        return vista

    async def _debounce_lote(self, room_id, sender) -> None:
        try:
            await asyncio.sleep(VENTANA_LOTE_SEGUNDOS)
        except asyncio.CancelledError:
            return

        clave = (room_id, sender)
        lock = self._get_user_lock(room_id, sender)

        try:
            async with lock:
                self.tareas_lote.pop(clave, None)
                ficheros = self.lotes_subida.pop(clave, [])
                if not ficheros:
                    return

                owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()

                if len(ficheros) == 1:
                    carpetas = await self._listar_carpetas(owner, repo, token)
                    self.pendientes_destino[clave] = {
                        "modo": "elegir_carpeta_lote", "ficheros": ficheros, "carpetas": carpetas,
                        "timestamp": int(time.time()),
                    }
                    nombre = ficheros[0]["nombre_archivo"]
                    vista_previa = self._vista_previa_transcripcion(ficheros[0]["texto_extraido"])
                    texto = (
                        f"He leído «{nombre}». Esto es lo que he entendido (revísalo antes de guardarlo):\n\n"
                        f"> {vista_previa}\n\n"
                        f"¿Dónde guardo «{nombre}»?\n\n{formatear_lista_carpetas(carpetas)}\n\n"
                        "Responde con el número de una carpeta, escribe el nombre de una carpeta "
                        "nueva (usa '/' para asignatura/tema, p.ej. Calculo/Tema3), o '0' para la raíz.\n"
                        "Si quieres cambiarle el nombre antes de guardarlo, escribe `nombre: <nuevo nombre>`."
                    )
                else:
                    self.pendientes_destino[clave] = {
                        "modo": "elegir_modo", "ficheros": ficheros, "timestamp": int(time.time()),
                    }
                    lineas = []
                    for f in ficheros:
                        vista_previa = self._vista_previa_transcripcion(f["texto_extraido"], longitud=120)
                        lineas.append(f"- **{f['nombre_archivo']}**: {vista_previa}")
                    texto = (
                        f"He recibido {len(ficheros)} ficheros. Esto es lo que he entendido de cada uno:\n"
                        + "\n".join(lineas) + "\n\n"
                        "¿Los guardo todos en el mismo sitio, o eliges carpeta para cada uno? "
                        "Responde 'todos' o 'uno por uno'."
                    )

                await self.client.send_text(room_id, texto)
        except Exception as exc:
            self.log.error(f"[github_bot] Error en _debounce_lote para {room_id}: {exc}")
            try:
                await self.client.send_text(
                    room_id,
                    f"⚠️ Error al preparar el guardado del fichero en el repositorio: {exc}\n"
                    "Por favor, intenta subir el archivo nuevamente o verifica la configuración del repositorio."
                )
            except Exception:
                pass

    async def _procesar_respuesta_destino(self, evt: MessageEvent, estado: dict) -> None:
        clave = (evt.room_id, evt.sender)
        respuesta = (evt.content.body or "").strip()

        if int(time.time()) - estado["timestamp"] > PENDIENTE_TTL_SEGUNDOS:
            self.pendientes_destino.pop(clave, None)
            await evt.reply("Han pasado más de 30 minutos desde que pregunté dónde guardar esos ficheros; los descarto.")
            return

        coincidencia_rename = PATRON_RENOMBRAR.match(respuesta)
        if coincidencia_rename:
            await self._procesar_renombrado(evt, estado, coincidencia_rename.group(1).strip())
            return

        if estado["modo"] == "elegir_modo":
            modo_todos = es_respuesta_modo_lote(respuesta)
            if modo_todos is None:
                await evt.reply("No te he entendido. Responde 'todos' o 'uno por uno'.")
                return

            owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
            carpetas = await self._listar_carpetas(owner, repo, token)
            estado["carpetas"] = carpetas
            estado["timestamp"] = int(time.time())

            if modo_todos:
                estado["modo"] = "elegir_carpeta_lote"
                self.pendientes_destino[clave] = estado
                await evt.reply(
                    f"¿Dónde los guardo todos?\n\n{formatear_lista_carpetas(carpetas)}\n\n"
                    "Responde con el número, escribe una carpeta nueva, o '0' para la raíz."
                )
            else:
                estado["modo"] = "elegir_carpeta_individual"
                estado["indice_actual"] = 0
                self.pendientes_destino[clave] = estado
                primero = estado["ficheros"][0]["nombre_archivo"]
                await evt.reply(
                    f"Vale, uno por uno. ¿Dónde guardo «{primero}»?\n\n{formatear_lista_carpetas(carpetas)}\n\n"
                    "Responde con el número, escribe una carpeta nueva, o '0' para la raíz.\n"
                    "Si quieres cambiarle el nombre, escribe `nombre: <nuevo nombre>`."
                )
            return

        if estado["modo"] == "elegir_carpeta_lote":
            try:
                carpeta = resolver_eleccion_carpeta(respuesta, estado["carpetas"])
            except ValueError as exc:
                await evt.reply(str(exc))
                return
            self.pendientes_destino.pop(clave, None)
            await self._guardar_ficheros_en_carpeta(evt, estado["ficheros"], carpeta)
            return

        if estado["modo"] == "elegir_carpeta_individual":
            try:
                carpeta = resolver_eleccion_carpeta(respuesta, estado["carpetas"])
            except ValueError as exc:
                await evt.reply(str(exc))
                return

            fichero_actual = estado["ficheros"][estado["indice_actual"]]
            await self._guardar_ficheros_en_carpeta(evt, [fichero_actual], carpeta)

            estado["indice_actual"] += 1
            if estado["indice_actual"] >= len(estado["ficheros"]):
                self.pendientes_destino.pop(clave, None)
                return

            estado["timestamp"] = int(time.time())
            self.pendientes_destino[clave] = estado
            siguiente = estado["ficheros"][estado["indice_actual"]]["nombre_archivo"]
            await evt.reply(
                f"¿Dónde guardo «{siguiente}»?\n\n{formatear_lista_carpetas(estado['carpetas'])}\n\n"
                "Responde con el número, escribe una carpeta nueva, o '0' para la raíz."
            )
            return

    async def _procesar_renombrado(self, evt: MessageEvent, estado: dict, nuevo_nombre: str) -> None:
        clave = (evt.room_id, evt.sender)

        if not nuevo_nombre:
            await evt.reply("Indica el nuevo nombre, por ejemplo: `nombre: Apuntes Tema 3`.")
            return

        if estado["modo"] == "elegir_carpeta_individual":
            fichero = estado["ficheros"][estado["indice_actual"]]
        elif estado["modo"] == "elegir_carpeta_lote" and len(estado["ficheros"]) == 1:
            fichero = estado["ficheros"][0]
        else:
            await evt.reply("Con varios ficheros a la vez no puedo saber a cuál te refieres. Responde 'uno por uno' primero.")
            return

        nombre_anterior = fichero["nombre_archivo"]
        _, _, extension = nombre_anterior.rpartition(".")
        if "." in nuevo_nombre or not extension:
            fichero["nombre_archivo"] = nuevo_nombre
        else:
            fichero["nombre_archivo"] = f"{nuevo_nombre}.{extension}"

        estado["timestamp"] = int(time.time())
        self.pendientes_destino[clave] = estado

        await evt.reply(
            f"Hecho, lo guardaré como «{fichero['nombre_archivo']}» (antes «{nombre_anterior}»). "
            "Dime ahora dónde lo guardo."
        )

    async def _guardar_ficheros_en_carpeta(self, evt: MessageEvent, ficheros: list, carpeta: Optional[str]) -> None:
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
                self.log.warning(f"[github_bot] Error subiendo fuente a GitHub: {exc}")
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

    async def _descargar_adjunto(self, evt: MessageEvent) -> bytes:
        if evt.content.file is not None:
            contenido_cifrado = await self.client.download_media(evt.content.file.url)
            return decrypt_attachment(
                contenido_cifrado,
                evt.content.file.key.key,
                evt.content.file.hashes["sha256"],
                evt.content.file.iv,
            )
        return await self.client.download_media(evt.content.url)

    async def _resolver_ruta_unica(
        self, evt: MessageEvent, nombre: str, owner: str, repo: str, headers: dict
    ) -> Optional[str]:
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

    # --------------------------------------------------------------------
    # API de Git (escritura) delegada en self.git
    # --------------------------------------------------------------------

    async def _obtener_sha_y_contenido_github(
        self, session, owner: str, repo: str, headers: dict, path: str
    ) -> Optional[dict]:
        token = headers.get("PRIVATE-TOKEN") or (headers.get("Authorization", "").replace("token ", "")) or self._obtener_git_token()
        return await self.git.obtener_info_y_contenido(session, owner, repo, token, path, self._semaforo_github)

    async def _subir_o_actualizar_archivo_github(
        self, owner: str, repo: str, token: str, path: str, contenido: str, branch: str, mensaje_commit: str
    ) -> bool:
        return await self.git.subir_o_actualizar_archivo(owner, repo, token, path, contenido, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)

    async def _append_log_okf(
        self, owner: str, repo: str, token: str, branch: str, entrada: str, mensaje_commit: str
    ) -> None:
        await self.git.append_log_okf(owner, repo, token, branch, entrada, mensaje_commit, self._semaforo_github)
        self._invalidar_cache()

    async def _obtener_agents_md(self, owner: str, repo: str, token: str) -> Optional[str]:
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

    # --------------------------------------------------------------------
    # Ingesta automática OKF (raw/ -> okf/concepts, okf/entities, okf/sources)
    # --------------------------------------------------------------------

    async def _ejecutar_ingest_automatico(
        self, evt: MessageEvent, owner: str, repo: str, token: str, branch: str,
        ruta_fuente_repo: str, nombre_archivo: str,
    ) -> None:
        """
        Tras guardar una fuente en bruto, la estructura automáticamente en
        okf/ siguiendo AGENTS.md. Si algo falla aquí, la fuente en raw/ ya
        quedó guardada de todas formas: este paso es un "extra" sobre la
        curación normal, nunca debe hacer perder el fichero que el estudiante
        acaba de subir.
        """
        try:
            agents_md = await self._obtener_agents_md(owner, repo, token)
            if not agents_md:
                await evt.reply(
                    f"«{nombre_archivo}» está guardado en `{ruta_fuente_repo}`, pero no he "
                    f"encontrado `{AGENTS_MD_PATH}` en el repo, así que no puedo estructurarlo "
                    "automáticamente en okf/. Revísalo cuando puedas."
                )
                return

            await evt.reply(f"Estructurando «{nombre_archivo}» en la BdC (okf/), un momento...")

            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
            async with aiohttp.ClientSession() as session:
                info_fuente = await self._obtener_sha_y_contenido_github(session, owner, repo, headers, ruta_fuente_repo)
            if info_fuente is None:
                raise RuntimeError(f"No he podido releer «{ruta_fuente_repo}» recién subido.")
            contenido_fuente = base64.b64decode(info_fuente["content"]).decode("utf-8")
            if len(contenido_fuente.splitlines()) > 350:
                await self._ejecutar_ingest_por_lotes(evt, owner, repo, token, branch, ruta_fuente_repo, nombre_archivo, contenido_fuente, agents_md)
                return

            timestamp_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            instruccion = construir_prompt_ingest(agents_md, ruta_fuente_repo, nombre_archivo, timestamp_iso)

            llm = self._crear_llm()
            respuesta = await llm.generar_texto(instruccion, contenido_fuente)
            resultado = parsear_respuesta_ingest(respuesta)

        except IngestError as exc:
            self.log.warning(f"[github_bot] Respuesta de INGEST inválida para '{ruta_fuente_repo}': {exc}")
            await evt.reply(
                f"«{nombre_archivo}» está guardado en `{ruta_fuente_repo}`, pero no he podido "
                f"estructurarlo automáticamente en okf/ ({exc}). Queda pendiente de curar a mano."
            )
            return
        except Exception as exc:
            self.log.warning(f"[github_bot] Error en ingesta automática de '{ruta_fuente_repo}': {exc}")
            await evt.reply(
                f"«{nombre_archivo}» está guardado en `{ruta_fuente_repo}`, pero ha fallado la "
                f"estructuración automática en okf/ ({exc}). Queda pendiente de curar a mano."
            )
            return

        creados, actualizados = [], []
        for fichero in resultado["ficheros"]:
            try:
                fue_actualizacion = await self._subir_o_actualizar_archivo_github(
                    owner, repo, token, fichero["path"], fichero["contenido"], branch,
                    mensaje_commit=f"INGEST automático de '{ruta_fuente_repo}' (por {evt.sender})",
                )
            except Exception as exc:
                self.log.warning(f"[github_bot] Error subiendo '{fichero['path']}' de la ingesta: {exc}")
                await evt.reply(f"No he podido guardar `{fichero['path']}`: {exc}")
                continue
            (actualizados if fue_actualizacion else creados).append(fichero["path"])

        if resultado["log_entry"]:
            try:
                await self._append_log_okf(
                    owner, repo, token, branch, resultado["log_entry"],
                    mensaje_commit=f"Log de INGEST automático de '{ruta_fuente_repo}'",
                )
            except Exception as exc:
                self.log.warning(f"[github_bot] Error haciendo append a {OKF_LOG_PATH}: {exc}")

        await self.tracker.log_curacion(evt.sender, evt.room_id, "ingest_automatico", ruta_fuente_repo)

        partes = [f"He estructurado «{nombre_archivo}» en la BdC."]
        if creados:
            partes.append("**Ficheros nuevos:**\n" + "\n".join(f"- `{p}`" for p in creados))
        if actualizados:
            partes.append("**Ficheros actualizados:**\n" + "\n".join(f"- `{p}`" for p in actualizados))
        if resultado["contradicciones"]:
            partes.append("**⚠️ Contradicciones detectadas:**\n" + "\n".join(f"- {c}" for c in resultado["contradicciones"]))
        if resultado["preguntas_seguimiento"]:
            partes.append("**Preguntas de seguimiento:**\n" + "\n".join(f"- {p}" for p in resultado["preguntas_seguimiento"]))

        await evt.reply("\n\n".join(partes))

    async def _ejecutar_ingest_por_lotes(
        self, evt: MessageEvent, owner: str, repo: str, token: str, branch: str,
        ruta_fuente_repo: str, nombre_archivo: str, contenido_fuente: str, agents_md: str
    ) -> None:
        lotes = dividir_en_lotes(contenido_fuente, max_lineas=250, solapamiento=30)
        total_lotes = len(lotes)
        await evt.reply(f"El documento «{nombre_archivo}» es extenso ({len(contenido_fuente.splitlines())} líneas). Iniciando extracción exhaustiva por {total_lotes} lotes en okf/...")

        llm = self._crear_llm()
        timestamp_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        creados_totales, actualizados_totales = [], []

        for i, texto_lote in enumerate(lotes, start=1):
            await evt.reply(f"📦 Procesando lote {i}/{total_lotes} de «{nombre_archivo}»...")
            instruccion = construir_prompt_ingest_lote(
                agents_md, ruta_fuente_repo, nombre_archivo, timestamp_iso, i, total_lotes
            )
            try:
                respuesta = await llm.generar_texto(instruccion, texto_lote)
                resultado = parsear_respuesta_ingest(respuesta)
            except Exception as exc:
                self.log.warning(f"[github_bot] Error procesando lote {i}/{total_lotes} de '{ruta_fuente_repo}': {exc}")
                await evt.reply(f"⚠️ Lote {i}/{total_lotes}: Hubo un problema extrayendo conceptos ({exc}). Continuando con el siguiente lote...")
                continue

            for fichero in resultado["ficheros"]:
                try:
                    fue_actualizacion = await self._subir_o_actualizar_archivo_github(
                        owner, repo, token, fichero["path"], fichero["contenido"], branch,
                        mensaje_commit=f"INGEST lote {i}/{total_lotes} de '{ruta_fuente_repo}' (por {evt.sender})",
                    )
                    (actualizados_totales if fue_actualizacion else creados_totales).append(fichero["path"])
                except Exception as exc:
                    self.log.warning(f"[github_bot] Error subiendo '{fichero['path']}' en lote {i}: {exc}")

            if resultado.get("log_entry"):
                try:
                    await self._append_log_okf(
                        owner, repo, token, branch, resultado["log_entry"],
                        mensaje_commit=f"Log INGEST lote {i}/{total_lotes} de '{ruta_fuente_repo}'",
                    )
                except Exception as exc:
                    self.log.warning(f"[github_bot] Error append log okf lote {i}: {exc}")

        await self.tracker.log_curacion(evt.sender, evt.room_id, "ingest_lotes", ruta_fuente_repo)
        resumen_partes = [f"✅ Ingesta por lotes completada al 100% para «{nombre_archivo}» ({total_lotes} lotes procesados)."]
        if creados_totales:
            resumen_partes.append(f"**Ficheros nuevos ({len(creados_totales)}):**\n" + "\n".join(f"- `{p}`" for p in sorted(set(creados_totales))[:20]))
        if actualizados_totales:
            resumen_partes.append(f"**Ficheros actualizados ({len(actualizados_totales)}):**\n" + "\n".join(f"- `{p}`" for p in sorted(set(actualizados_totales))[:20]))
        await evt.reply("\n\n".join(resumen_partes))

    @command.new(
        name="ingest_lotes",
        help="Extrae el 100% de conceptos por lotes de un fichero largo de raw/: !ingest_lotes [tema:<...>]",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def ingest_lotes_handler(self, evt: MessageEvent, texto: str = "") -> None:
        token = self._obtener_git_token()
        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        branch = self.config["default_branch"] or "main"

        _, tema, _ = _extraer_modificadores(texto)
        if not tema:
            await evt.reply("Indica la ruta del fichero de raw/ a ingestar. Ejemplo: `!ingest_lotes [tema:raw/00Libro de Teoria Musical - Nestor Crespo-1784644777.md]`.")
            return

        if not tema.startswith("raw/"):
            tema = f"raw/{tema}" if not tema.endswith(".md") else f"raw/{tema}"

        await evt.reply(f"Leyendo `{tema}` del repositorio para ingesta por lotes...")
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        async with aiohttp.ClientSession() as session:
            info_fuente = await self._obtener_sha_y_contenido_github(session, owner, repo, headers, tema)
        if not info_fuente:
            await evt.reply(f"No he encontrado o no he podido leer `{tema}` en el repositorio.")
            return

        contenido_fuente = base64.b64decode(info_fuente["content"]).decode("utf-8")
        agents_md = await self._obtener_agents_md(owner, repo, token)
        if not agents_md:
            await evt.reply("No he encontrado AGENTS.md en el repositorio para guiar la ingesta.")
            return

        nombre_archivo = tema.split("/")[-1]
        await self._ejecutar_ingest_por_lotes(evt, owner, repo, token, branch, tema, nombre_archivo, contenido_fuente, agents_md)

    async def _borrar_archivo_github(
        self, owner: str, repo: str, token: str, path: str, branch: str, sha: str = "", mensaje_commit: str = ""
    ) -> None:
        await self.git.borrar_archivo(owner, repo, token, path, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)

    async def _mover_archivo_github(
        self, owner: str, repo: str, token: str, ruta_antigua: str, ruta_nueva: str, branch: str, sender: str
    ) -> None:
        await self.git.mover_archivo(owner, repo, token, ruta_antigua, ruta_nueva, branch, sender, self._semaforo_github, self._invalidar_cache)

    async def _subir_archivo_github(
        self, owner: str, repo: str, token: str, path: str, contenido: str, branch: str, mensaje_commit: str
    ) -> None:
        await self.git.subir_archivo(owner, repo, token, path, contenido, branch, mensaje_commit, self._semaforo_github, self._invalidar_cache)

    # --------------------------------------------------------------------
    # Comandos de información y estadísticas
    # --------------------------------------------------------------------

    @command.new(
        name="pregunta",
        help="Pregunta sobre la documentación del repo: !pregunta [tema:<carpeta/fichero>] <texto>",
    )
    @command.argument("texto", pass_raw=True, required=True)
    async def pregunta_handler(self, evt: MessageEvent, texto: str) -> None:
        token = self._obtener_git_token()
        owner = self.config["default_owner"]
        repo = self.config["default_repo"]

        texto, tema, _ = _extraer_modificadores(texto)
        if not texto:
            await evt.reply("Falta la pregunta. Formato: `!pregunta [tema:<carpeta/fichero>] <texto>`.")
            return

        await evt.reply("Buscando en la documentación, un momento...")

        contenido_docs = await self._obtener_documentacion(owner, repo, token, tema)
        if not contenido_docs and tema:
            await evt.reply(f"No he encontrado ningún fichero de la BdC que coincida con «{tema}».")
            return
        if not contenido_docs:
            await evt.reply("No he podido leer la documentación del repositorio.")
            return

        provider = self._crear_llm()
        try:
            respuesta = await provider.preguntar(texto, contenido_docs)
        except Exception as exc:
            await evt.reply(f"Error al consultar el modelo: {exc}")
            return

        # T6: Usar LaTeX
        await self._responder_con_latex(evt, respuesta)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "pregunta", texto)
        await self.tracker.log_qa(evt.sender, evt.room_id, "pregunta", texto, respuesta, "informativo")

    @command.new(name="ficheros", help="Lista los archivos .md/.txt encontrados en el repo de la BdC")
    async def ficheros_handler(self, evt: MessageEvent) -> None:
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

    @command.new(name="misestadisticas", help="Muestra tus métricas de trazabilidad en la BdC")
    async def estadisticas_handler(self, evt: MessageEvent) -> None:
        try:
            stats = await self.tracker.obtener_estadisticas(evt.sender)
        except Exception as exc:
            self.log.exception(f"[github_bot] Error consultando el tracker en !misestadisticas: {exc}")
            await evt.reply("He tenido un problema interno consultando tus estadísticas. Prueba en un momento.")
            return

        if stats["total_ejercicios"] > 0:
            porcentaje_acierto = round(100 * stats["ejercicios_correctos"] / stats["total_ejercicios"])
            linea_ejercicios = (
                f"- Ejercicios realizados: {stats['total_ejercicios']} "
                f"({stats['ejercicios_correctos']} correctos, {porcentaje_acierto}%)"
            )
        else:
            linea_ejercicios = "- Ejercicios realizados: 0"

        # T3: Incluir métricas de curación
        mensaje = (
            f"Estadísticas de {evt.sender}:\n"
            f"- Interacciones totales con el bot: {stats['total_interacciones']}\n"
            f"- Fuentes en bruto aportadas a la BdC: {stats['total_fuentes_raw']}\n"
            f"- Acciones de curación en la BdC: {stats['total_curaciones']} "
            f"(subidas: {stats['curaciones_subidas']}, movidos: {stats['curaciones_movidos']}, borrados: {stats['curaciones_borrados']})\n"
            f"{linea_ejercicios}"
        )
        await evt.reply(mensaje)

    @command.new(name="trazabilidad", help="Consulta tu historial de aprendizaje y curación", require_subcommand=False)
    async def trazabilidad_handler(self, evt: MessageEvent) -> None:
        stats = await self.tracker.obtener_estadisticas(evt.sender)
        qa_list = await self.tracker.obtener_todas_qa(evt.sender, limite=1000)
        texto = (
            f"📊 **Panel de Trazabilidad de {evt.sender}**\n\n"
            f"- **Total interacciones**: {stats['total_interacciones']}\n"
            f"- **Preguntas y ejercicios (Q&A)**: {len(qa_list)} registrados en historial\n"
            f"- **Acciones de curación en BdC**: {stats['total_curaciones']} (subidas: {stats['curaciones_subidas']}, movidos: {stats['curaciones_movidos']}, borrados: {stats['curaciones_borrados']})\n\n"
            "**Opciones de consulta detallada:**\n"
            "- `!trazabilidad qa [limite]` — Ver todas las preguntas, tus respuestas y la corrección/evaluación del bot.\n"
            "- `!trazabilidad interacciones [limite]` — Ver listado cronológico de todos los comandos e interacciones.\n"
            "- `!trazabilidad curacion [limite]` — Ver historial de documentos subidos, movidos y borrados.\n"
            "- `!trazabilidad exportar` — Genera y descarga un informe completo en Markdown con todo tu historial."
        )
        await evt.reply(texto)

    @trazabilidad_handler.subcommand("qa", help="Muestra el historial completo de preguntas, respuestas y evaluations")
    @command.argument("limite", pass_raw=True, required=False)
    async def trazabilidad_qa_handler(self, evt: MessageEvent, limite: str = "15") -> None:
        try:
            lim_int = min(int((limite or "15").strip()), 50)
        except ValueError:
            lim_int = 15
        qa_list = await self.tracker.obtener_todas_qa(evt.sender, limite=lim_int)
        if not qa_list:
            await evt.reply("No tienes preguntas ni respuestas registradas en el historial todavía.")
            return

        partes = [f"**Historial de Preguntas y Respuestas (Últimas {len(qa_list)}):**"]
        for idx, item in enumerate(qa_list, 1):
            fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["timestamp"]))
            eval_txt = f"\n  - *Evaluación*: {item['evaluacion']}" if item["evaluacion"] else ""
            partes.append(
                f"\n**{idx}. [{item['tipo'].upper()} — {fecha}]**\n"
                f"  - *Pregunta*: {item['pregunta']}\n"
                f"  - *Respuesta*: {item['respuesta']}"
                f"{eval_txt}"
            )
        await self._responder_con_latex(evt, "\n".join(partes))

    @trazabilidad_handler.subcommand("interacciones", help="Muestra el listado cronológico de interacciones con el bot")
    @command.argument("limite", pass_raw=True, required=False)
    async def trazabilidad_interacciones_handler(self, evt: MessageEvent, limite: str = "20") -> None:
        try:
            lim_int = min(int((limite or "20").strip()), 50)
        except ValueError:
            lim_int = 20
        interacciones = await self.tracker.obtener_todas_interacciones(evt.sender, limite=lim_int)
        if not interacciones:
            await evt.reply("No tienes interacciones registradas en el historial todavía.")
            return

        partes = [f"**Historial de Interacciones con el Bot (Últimas {len(interacciones)}):**"]
        for idx, item in enumerate(interacciones, 1):
            fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["timestamp"]))
            cont = f" — `{item['contenido']}`" if item["contenido"] else ""
            partes.append(f"{idx}. `[{fecha}]` **{item['tipo']}**{cont}")
        await evt.reply("\n".join(partes))

    @trazabilidad_handler.subcommand("curacion", help="Muestra el historial de subidas, movidos y borrados de la BdC")
    @command.argument("limite", pass_raw=True, required=False)
    async def trazabilidad_curacion_handler(self, evt: MessageEvent, limite: str = "20") -> None:
        try:
            lim_int = min(int((limite or "20").strip()), 50)
        except ValueError:
            lim_int = 20
        curaciones = await self.tracker.obtener_todas_curaciones(evt.sender, limite=lim_int)
        if not curaciones:
            await evt.reply("No tienes acciones de curación registradas todavía.")
            return

        partes = [f"**Historial de Curación en la BdC (Últimas {len(curaciones)}):**"]
        for idx, item in enumerate(curaciones, 1):
            fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["timestamp"]))
            partes.append(f"{idx}. `[{fecha}]` **{item['tipo'].upper()}**: `{item['ruta']}`")
        await evt.reply("\n".join(partes))

    @trazabilidad_handler.subcommand("exportar", help="Genera y envía un informe completo en Markdown de tu trazabilidad")
    async def trazabilidad_exportar_handler(self, evt: MessageEvent) -> None:
        await evt.reply("Generando tu informe de trazabilidad en Markdown...")
        stats = await self.tracker.obtener_estadisticas(evt.sender)
        qa_list = await self.tracker.obtener_todas_qa(evt.sender, limite=1000)
        interacciones = await self.tracker.obtener_todas_interacciones(evt.sender, limite=1000)
        curaciones = await self.tracker.obtener_todas_curaciones(evt.sender, limite=1000)

        lineas = [
            "# Informe de Trazabilidad de Aprendizaje y Curación",
            f"**Estudiante:** `{evt.sender}`\n**Fecha:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            "## 1. Resumen de Métricas",
            f"- Total interacciones: {stats['total_interacciones']}",
            f"- Preguntas y ejercicios respondidos: {len(qa_list)}",
            f"- Ejercicios correctos: {stats['ejercicios_correctos']}",
            f"- Acciones de curación en BdC: {stats['total_curaciones']} (subidas: {stats['curaciones_subidas']}, movidos: {stats['curaciones_movidos']}, borrados: {stats['curaciones_borrados']})\n",
            "## 2. Historial de Preguntas y Respuestas (Q&A)",
        ]
        if not qa_list:
            lineas.append("*Sin registros de preguntas y respuestas.*")
        else:
            for idx, item in enumerate(qa_list, 1):
                f_txt = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["timestamp"]))
                lineas.extend([
                    f"### {idx}. {item['tipo'].upper()} ({f_txt})",
                    f"- **Pregunta**: {item['pregunta']}",
                    f"- **Respuesta estudiante/bot**: {item['respuesta']}",
                    f"- **Evaluación/Feedback**: {item['evaluacion']}\n",
                ])

        lineas.append("## 3. Historial de Curación de Contenidos")
        if not curaciones:
            lineas.append("*Sin registros de curación.*")
        else:
            for item in curaciones:
                f_txt = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["timestamp"]))
                lineas.append(f"- `[{f_txt}]` **{item['tipo'].upper()}**: `{item['ruta']}`")

        lineas.append("\n## 4. Registro Cronológico de Interacciones")
        if not interacciones:
            lineas.append("*Sin interacciones registradas.*")
        else:
            for item in interacciones[:100]:
                f_txt = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["timestamp"]))
                cont = f" — {item['contenido']}" if item['contenido'] else ""
                lineas.append(f"- `[{f_txt}]` **{item['tipo']}**{cont}")

        contenido_md = "\n".join(lineas)
        data = contenido_md.encode("utf-8")
        try:
            mxc_uri = await self.client.upload_media(data, mime_type="text/markdown", filename="trazabilidad.md")
            await self.client.send_file(
                evt.room_id, url=mxc_uri, info={"mimetype": "text/markdown", "size": len(data)},
                file_name="trazabilidad.md",
            )
        except Exception as exc:
            self.log.warning(f"[github_bot] Error subiendo informe de trazabilidad: {exc}")
            await evt.reply("No pude adjuntar el archivo, envío el resumen aquí:\n\n" + "\n".join(lineas[:40]))

    # --------------------------------------------------------------------
    # Comandos de curación explícita (!documento, !borrar, !mover, !carpeta)
    # --------------------------------------------------------------------

    @command.new(name="documento", help="Información de un documento concreto: !documento <nombre>")
    @command.argument("nombre", pass_raw=True, required=True)
    async def documento_handler(self, evt: MessageEvent, nombre: str) -> None:
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
            self.log.exception(f"[github_bot] Error consultando el tracker en !documento: {exc}")
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

    @command.new(name="borrar", help="Borra un documento de la BdC (pide confirmación): !borrar <nombre>")
    @command.argument("nombre", pass_raw=True, required=True)
    async def borrar_handler(self, evt: MessageEvent, nombre: str) -> None:
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

    async def _procesar_confirmacion_borrado(self, evt: MessageEvent, estado: dict) -> None:
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
            self.log.warning(f"[github_bot] Error borrando '{ruta}' de GitHub: {exc}")
            await evt.reply(f"No he podido borrar «{ruta}»: {exc}")
            return

        await self.tracker.eliminar_fuentes_por_ruta(ruta)
        await evt.reply(f"«{ruta}» borrado de la BdC.")
        # T3: Registro en curaciones
        await self.tracker.log_curacion(evt.sender, evt.room_id, "borrado", ruta)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "documento_borrado", ruta)

    async def _procesar_confirmacion_borrado_carpeta(self, evt: MessageEvent, estado: dict) -> None:
        clave = (evt.room_id, evt.sender)
        self.pendientes_borrado_carpeta.pop(clave, None)

        if int(time.time()) - estado["timestamp"] > CONFIRMACION_BORRADO_TTL_SEGUNDOS:
            await evt.reply("Han pasado más de 5 minutos, doy el borrado de la carpeta por cancelado.")
            return

        if evt.content.body.strip().lower() != "confirmar":
            await evt.reply("Borrado de carpeta cancelado.")
            return

        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()
        branch = self.config["default_branch"] or "main"
        carpeta = estado["carpeta"]
        ficheros = estado["ficheros"]

        await evt.reply(f"Borrando los {len(ficheros)} archivo(s) de la carpeta «{carpeta}», un momento...")

        errores = []
        for f in ficheros:
            try:
                await self._borrar_archivo_github(
                    owner, repo, token, f["path"], branch, f["sha"],
                    mensaje_commit=f"Borrar carpeta '{carpeta}': '{f['path']}' (por {evt.sender})",
                )
                await self.tracker.eliminar_fuentes_por_ruta(f["path"])
                await self.tracker.log_curacion(evt.sender, evt.room_id, "borrado", f["path"])
            except Exception as exc:
                self.log.warning(f"[github_bot] Error borrando '{f['path']}': {exc}")
                errores.append(f"{f['path']} ({exc})")

        self._invalidar_cache()
        if errores:
            await evt.reply(f"⚠️ Se ha borrado parte de la carpeta «{carpeta}», pero hubo errores en {len(errores)} archivo(s):\n" + "\n".join(f"- {e}" for e in errores[:5]))
        else:
            await evt.reply(f"✅ Carpeta «{carpeta}» y todos sus contenidos ({len(ficheros)} archivo(s)) borrados de la BdC.")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "carpeta_borrada", carpeta)

    @command.new(name="mover", help="Mueve un documento de carpeta: !mover <nombre> -> <carpeta_destino|raiz>")
    @command.argument("texto", pass_raw=True, required=True)
    async def mover_handler(self, evt: MessageEvent, texto: str) -> None:
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

        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()
        branch = self.config["default_branch"] or "main"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        ruta_antigua = await self._resolver_ruta_unica(evt, nombre, owner, repo, headers)
        if ruta_antigua is None:
            return

        nombre_fichero = ruta_antigua.rsplit("/", 1)[-1]
        ruta_nueva = f"{carpeta_destino}/{nombre_fichero}" if carpeta_destino else nombre_fichero

        if ruta_nueva == ruta_antigua:
            await evt.reply(f"«{ruta_antigua}» ya está en esa carpeta.")
            return

        try:
            await self._mover_archivo_github(owner, repo, token, ruta_antigua, ruta_nueva, branch, evt.sender)
        except Exception as exc:
            self.log.warning(f"[github_bot] Error moviendo '{ruta_antigua}' -> '{ruta_nueva}': {exc}")
            await evt.reply(f"No he podido mover «{ruta_antigua}»: {exc}")
            return

        await self.tracker.actualizar_ruta_fuente(ruta_antigua, ruta_nueva)
        await evt.reply(f"«{ruta_antigua}» movido a `{ruta_nueva}`.")
        # T3: Registro en curaciones
        await self.tracker.log_curacion(evt.sender, evt.room_id, "movido", f"{ruta_antigua} -> {ruta_nueva}")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "documento_movido", f"{ruta_antigua} -> {ruta_nueva}")

    @command.new(name="carpeta", help="Gestiona las carpetas/asignaturas de la BdC", require_subcommand=False)
    async def carpeta_handler(self, evt: MessageEvent) -> None:
        await evt.reply("Usa `!carpeta crear <ruta>`, `!carpeta borrar <ruta>` o `!carpeta listar`.")

    @carpeta_handler.subcommand("crear", help="Crea una carpeta nueva: !carpeta crear <ruta>")
    @command.argument("ruta", pass_raw=True, required=True)
    async def carpeta_crear_handler(self, evt: MessageEvent, ruta: str) -> None:
        carpeta = sanitizar_carpeta(ruta)
        if not carpeta:
            await evt.reply("Nombre de carpeta inválido. Prueba p.ej. `Calculo/Tema3`.")
            return

        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()
        branch = self.config["default_branch"] or "main"

        marca_tiempo = int(time.time())
        ruta_placeholder = f"{carpeta}/.gitkeep"
        contenido = f"Carpeta creada por {evt.sender} el {marca_tiempo}.\n"

        try:
            await self._subir_archivo_github(
                owner, repo, token, ruta_placeholder, contenido, branch,
                mensaje_commit=f"Crear carpeta '{carpeta}' (por {evt.sender})",
            )
        except Exception as exc:
            self.log.warning(f"[github_bot] Error creando carpeta: {exc}")
            await evt.reply(f"No he podido crear la carpeta «{carpeta}».")
            return

        await evt.reply(f"Carpeta «{carpeta}» creada.")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "carpeta_creada", carpeta)

    @carpeta_handler.subcommand("listar", help="Lista las carpetas existentes en la BdC")
    async def carpeta_listar_handler(self, evt: MessageEvent) -> None:
        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()

        carpetas = await self._listar_carpetas(owner, repo, token)
        if not carpetas:
            await evt.reply("Todavía no hay carpetas creadas. Usa `!carpeta crear <nombre>`.")
            return

        await evt.reply("Carpetas en la BdC:\n" + "\n".join(f"- {c}" for c in carpetas))

    @carpeta_handler.subcommand("borrar", help="Borra una carpeta de la BdC: !carpeta borrar <ruta>")
    @command.argument("ruta", pass_raw=True, required=True)
    async def carpeta_borrar_handler(self, evt: MessageEvent, ruta: str) -> None:
        carpeta = sanitizar_carpeta(ruta)
        if not carpeta:
            await evt.reply("Nombre de carpeta inválido. Prueba p.ej. `Calculo/Tema3`.")
            return

        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()
        branch = self.config["default_branch"] or "main"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        await evt.reply(f"Revisando el contenido de la carpeta «{carpeta}» en la BdC...")
        async with aiohttp.ClientSession() as session:
            ficheros = await self._recorrer_carpeta_con_sha(session, owner, repo, headers, carpeta)

        if not ficheros:
            await evt.reply(f"La carpeta «{carpeta}» no existe o ya está vacía en la BdC.")
            return

        ficheros_reales = [f for f in ficheros if not f["path"].endswith(".gitkeep")]

        if not ficheros_reales:
            await evt.reply(f"Borrando carpeta vacía «{carpeta}»...")
            for f in ficheros:
                try:
                    await self._borrar_archivo_github(
                        owner, repo, token, f["path"], branch, f["sha"],
                        mensaje_commit=f"Borrar carpeta vacía '{carpeta}' (por {evt.sender})",
                    )
                    await self.tracker.eliminar_fuentes_por_ruta(f["path"])
                except Exception as exc:
                    self.log.warning(f"[github_bot] Error borrando {f['path']}: {exc}")
            self._invalidar_cache()
            await evt.reply(f"✅ Carpeta vacía «{carpeta}» eliminada de la BdC.")
            await self.tracker.log_interaccion(evt.sender, evt.room_id, "carpeta_borrada", carpeta)
            return

        lista_muestra = "\n".join(f"- `{f['path']}`" for f in ficheros_reales[:10])
        aviso_mas = f"\n... y {len(ficheros_reales) - 10} archivo(s) más." if len(ficheros_reales) > 10 else ""
        self.pendientes_borrado_carpeta[(evt.room_id, evt.sender)] = {
            "carpeta": carpeta,
            "ficheros": ficheros,
            "timestamp": int(time.time()),
        }
        await evt.reply(
            f"⚠️ La carpeta «{carpeta}» **no está vacía**, contiene **{len(ficheros_reales)} archivo(s)**:\n{lista_muestra}{aviso_mas}\n\n"
            f"Vas a borrar la carpeta y **todo su contenido** de forma permanente. "
            f"Escribe `confirmar` en los próximos {CONFIRMACION_BORRADO_TTL_SEGUNDOS // 60} minutos para continuar, o ignora este mensaje para cancelar."
        )

    # --------------------------------------------------------------------
    # Herramientas de estudio interactivas
    # --------------------------------------------------------------------

    async def _plantear_pregunta(
        self, evt: MessageEvent, tipo: str, generador, tema: str = "", tipo_contenido: str = ""
    ) -> None:
        owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
        contenido_docs = await self._obtener_documentacion(owner, repo, token, tema)
        if not contenido_docs and tema:
            await evt.reply(f"No he encontrado ningún fichero en la BdC que coincida con «{tema}».")
            return
        if not contenido_docs:
            await evt.reply("No he podido leer la documentación del repositorio.")
            return

        try:
            generada = await generador(contenido_docs, self._crear_llm(), tipo_contenido)
        except Exception as exc:
            await evt.reply(f"No he podido generar la pregunta: {exc}")
            return

        self.pendientes[(evt.room_id, evt.sender)] = {
            "tipo": tipo,
            "concepto": generada["concepto"],
            "pregunta": generada["pregunta"],
            "timestamp": int(time.time()),
            "contenido_docs": contenido_docs,
            "tema": tema,
        }
        # T6: Renderizar fórmulas LaTeX en la pregunta
        texto_md = f"**{generada['concepto']}**\n\n{generada['pregunta']}"
        await self._responder_con_latex(evt, texto_md)

    async def _evaluar_pendiente(self, evt: MessageEvent, pendiente: dict) -> None:
        clave = (evt.room_id, evt.sender)
        contenido_docs = pendiente.get("contenido_docs")
        if contenido_docs is None:
            owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
            contenido_docs = await self._obtener_documentacion(owner, repo, token, pendiente.get("tema", ""))

        try:
            resultado = await evaluar_respuesta(
                pendiente["tipo"], pendiente["concepto"], pendiente["pregunta"],
                evt.content.body, contenido_docs, self._crear_llm(),
            )
        except EstudioError as exc:
            self.pendientes[clave] = pendiente
            await evt.reply(f"No he podido corregir la respuesta: {exc}")
            return
        except Exception as exc:
            self.pendientes[clave] = pendiente
            self.log.warning(f"[github_bot] Error del LLM corrigiendo la respuesta: {exc}")
            await evt.reply(f"No he podido corregir tu respuesta: {exc}\nTu pregunta sigue pendiente.")
            return

        emoji = "✅" if resultado["correcto"] else "❌"
        # T6: Renderizar fórmulas en el feedback
        await self._responder_con_latex(evt, f"{emoji} {resultado['feedback']}")

        resultado_txt = "correcto" if resultado["correcto"] else "incorrecto"
        await self.tracker.log_ejercicio(evt.sender, evt.room_id, resultado_txt, tipo=pendiente["tipo"])
        await self.tracker.log_interaccion(
            evt.sender, evt.room_id, pendiente["tipo"], f"{pendiente['concepto']}: {resultado_txt}"
        )
        await self.tracker.registrar_concepto(evt.sender, pendiente["concepto"], resultado["correcto"])
        await self.tracker.log_qa(
            evt.sender, evt.room_id, pendiente["tipo"],
            f"[{pendiente['concepto']}] {pendiente['pregunta']}",
            evt.content.body,
            f"{emoji} {resultado['feedback']}",
        )

        if pendiente["tipo"] == "repaso_tema":
            await self._avanzar_repaso_tema(evt, pendiente, resultado["correcto"])

    async def _avanzar_repaso_tema(self, evt: MessageEvent, pendiente: dict, acierto: bool) -> None:
        clave = (evt.room_id, evt.sender)
        total = pendiente["total"]
        correctos = pendiente["correctos"] + (1 if acierto else 0)
        cola = pendiente["cola"]

        if not cola:
            porcentaje = round(100 * correctos / total) if total else 0
            await evt.reply(f"Repaso del tema terminado: {correctos}/{total} correctos ({porcentaje}%).")
            await self.tracker.log_interaccion(
                evt.sender, evt.room_id, "repaso_tema", f"sesión completa: {correctos}/{total} correctos"
            )
            return

        siguiente, *resto = cola
        avanzado = pendiente["avanzado"] + 1
        self.pendientes[clave] = {
            "tipo": "repaso_tema",
            "concepto": siguiente["concepto"],
            "pregunta": siguiente["pregunta"],
            "timestamp": int(time.time()),
            "cola": resto,
            "contenido_docs": pendiente["contenido_docs"],
            "avanzado": avanzado,
            "total": total,
            "correctos": correctos,
        }
        texto_md = f"**({avanzado}/{total}) {siguiente['concepto']}**\n\n{siguiente['pregunta']}"
        await self._responder_con_latex(evt, texto_md)

    @command.new(
        name="flashcard",
        help="Pregunta de repaso sobre un concepto: !flashcard [tema:<...>] [tipo:<...>]",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def flashcard_handler(self, evt: MessageEvent, texto: str = "") -> None:
        _, tema, tipo_contenido = _extraer_modificadores(texto)
        await self._plantear_pregunta(
            evt, tipo="flashcard", generador=generar_flashcard, tema=tema, tipo_contenido=tipo_contenido
        )

    @command.new(
        name="ejercicio",
        help="Repaso con ejercicios: !ejercicio [tema:<...>] [tipo:<...>] o !ejercicio <tu ejercicio/solución>",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def ejercicio_handler(self, evt: MessageEvent, texto: str = "") -> None:
        resto, tema, tipo_contenido = _extraer_modificadores(texto)
        if not resto:
            await self._plantear_pregunta(
                evt, tipo="ejercicio", generador=generar_ejercicio, tema=tema, tipo_contenido=tipo_contenido
            )
            return

        owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
        contenido_docs = await self._obtener_documentacion(owner, repo, token, tema)
        if not contenido_docs and tema:
            await evt.reply(f"No he encontrado ningún fichero de la BdC que coincida con «{tema}».")
            return
        if not contenido_docs:
            await evt.reply("No he podido leer la documentación del repositorio.")
            return

        try:
            resultado = await evaluar_respuesta(
                "ejercicio", "ejercicio propuesto por el estudiante",
                "El estudiante ha propuesto y/o resuelto un ejercicio por su cuenta.",
                resto, contenido_docs, self._crear_llm(),
            )
        except Exception as exc:
            await evt.reply(f"No he podido corregir la respuesta: {exc}")
            return

        emoji = "✅" if resultado["correcto"] else "❌"
        await self._responder_con_latex(evt, f"{emoji} {resultado['feedback']}")

        resultado_txt = "correcto" if resultado["correcto"] else "incorrecto"
        await self.tracker.log_ejercicio(evt.sender, evt.room_id, resultado_txt, tipo="ejercicio")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "ejercicio", resto)

    @command.new(
        name="concepto",
        help="Pregunta la definición de un concepto: !concepto [nombre] [tema:<...>] [tipo:<...>]",
    )
    @command.argument("nombre", pass_raw=True, required=False)
    async def concepto_handler(self, evt: MessageEvent, nombre: str = "") -> None:
        await self._plantear_pregunta_concepto(
            evt, tipo="concepto", nombre=nombre,
            plantilla_pregunta="¿Cuál es la definición de «{concepto}»?",
        )

    @command.new(
        name="feynman",
        help="Técnica Feynman (explícamelo con tus palabras): !feynman [concepto] [tema:<...>] [tipo:<...>]",
    )
    @command.argument("nombre", pass_raw=True, required=False)
    async def feynman_handler(self, evt: MessageEvent, nombre: str = "") -> None:
        await self._plantear_pregunta_concepto(
            evt, tipo="feynman", nombre=nombre,
            plantilla_pregunta="Explícame con tus propias palabras qué es «{concepto}» (sin copiarlo de los apuntes).",
        )

    async def _plantear_pregunta_concepto(
        self, evt: MessageEvent, tipo: str, nombre: str, plantilla_pregunta: str
    ) -> None:
        concepto, tema, tipo_contenido = _extraer_modificadores(nombre)

        owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
        contenido_docs = await self._obtener_documentacion(owner, repo, token, tema)
        if not contenido_docs and tema:
            await evt.reply(f"No he encontrado ningún fichero de la BdC que coincida con «{tema}».")
            return
        if not contenido_docs:
            await evt.reply("No he podido leer la documentación del repositorio.")
            return

        if not concepto:
            try:
                concepto = await elegir_concepto(contenido_docs, self._crear_llm(), tipo_contenido)
            except Exception as exc:
                await evt.reply(f"No he podido elegir un concepto: {exc}")
                return

        pregunta = plantilla_pregunta.format(concepto=concepto)
        self.pendientes[(evt.room_id, evt.sender)] = {
            "tipo": tipo, "concepto": concepto, "pregunta": pregunta, "timestamp": int(time.time()),
            "contenido_docs": contenido_docs,
            "tema": tema,
        }
        await self._responder_con_latex(evt, pregunta)

    @command.new(
        name="repasartema",
        help="Repasa TODOS los conceptos de un tema, uno a uno: !repasartema [tema:<...>] [tipo:<...>]",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def repasartema_handler(self, evt: MessageEvent, texto: str = "") -> None:
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
            self.log.warning(f"[github_bot] Error listando conceptos en !repasartema: {exc}")
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
            self.log.warning(f"[github_bot] Error generando lote de preguntas: {exc}")
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

    # --------------------------------------------------------------------
    # T5: Nuevo comando !ejerciciostema
    # --------------------------------------------------------------------

    @command.new(
        name="ejerciciostema",
        help="Busca ejercicios o problemas en la BdC que apliquen una técnica/teorema: !ejerciciostema <técnica>",
    )
    @command.argument("tecnica", pass_raw=True, required=True)
    async def ejerciciostema_handler(self, evt: MessageEvent, tecnica: str) -> None:
        tecnica = (tecnica or "").strip()
        if not tecnica:
            await evt.reply("Indica qué técnica, teorema o herramienta quieres buscar en los ejercicios de la BdC. Ejemplo: `!ejerciciostema integración por partes`")
            return

        await evt.reply(f"Buscando ejercicios en la BdC que apliquen «{tecnica}», un momento...")

        owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
        contenido_docs = await self._obtener_documentacion(owner, repo, token)
        if not contenido_docs:
            await evt.reply("No he podido leer la documentación del repositorio.")
            return

        provider = self._crear_llm()
        try:
            ejercicios = await buscar_ejercicios_por_tecnica(tecnica, contenido_docs, provider)
        except Exception as exc:
            self.log.warning(f"[github_bot] Error buscando ejercicios por técnica: {exc}")
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

    @command.new(name="resumen", help="Resumen de lo que has repasado en esta sesión")
    async def resumen_handler(self, evt: MessageEvent) -> None:
        desde = int(time.time()) - SESION_VENTANA_SEGUNDOS
        interacciones = await self.tracker.obtener_interacciones_recientes(evt.sender, desde)
        if not interacciones:
            horas = SESION_VENTANA_SEGUNDOS // 3600
            await evt.reply(f"No tienes actividad registrada en las últimas {horas} horas.")
            return

        owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
        contenido_docs = await self._obtener_documentacion(owner, repo, token)

        try:
            resumen = await generar_resumen_sesion(interacciones, contenido_docs, self._crear_llm())
        except Exception as exc:
            await evt.reply(f"No he podido generar el resumen: {exc}")
            return

        await self._responder_con_latex(evt, resumen)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "resumen", "")

    @command.new(name="mapa", help="Qué conceptos dominas y cuáles tienes que repasar")
    async def mapa_handler(self, evt: MessageEvent) -> None:
        conceptos = await self.tracker.obtener_mapa_conceptos(evt.sender)
        if not conceptos:
            await evt.reply("Todavía no tienes conceptos registrados. Prueba con !concepto, !flashcard o !feynman.")
            return

        dominados = [c for c in conceptos if c["dominado"]]
        en_progreso = [c for c in conceptos if not c["dominado"]]

        partes = []
        if dominados:
            lineas = "\n".join(f"- {c['concepto']} ({c['aciertos']}/{c['intentos']})" for c in dominados)
            partes.append(f"**Dominados:**\n{lineas}")
        if en_progreso:
            lineas = "\n".join(f"- {c['concepto']} ({c['aciertos']}/{c['intentos']})" for c in en_progreso)
            partes.append(f"**Por repasar:**\n{lineas}")

        await self._responder_con_latex(evt, "\n\n".join(partes))
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "mapa", "")

    # --------------------------------------------------------------------
    # Comando !ayuda
    # --------------------------------------------------------------------

    AYUDA_TEXTO = (
        "**Comandos disponibles:**\n\n"
        "- `!pregunta [tema:<...>] <texto>` — Pregunta sobre el contenido de la BdC.\n"
        "- `!ficheros` — Lista los archivos de la BdC.\n"
        "- `!documento <nombre>` — Información de un documento concreto.\n"
        "- `!borrar <nombre>` — Borra un documento de la BdC (pide confirmación).\n"
        "- `!mover <nombre> -> <carpeta_destino|raiz>` — Mueve un documento a otra carpeta.\n"
        "- `!carpeta crear <ruta>` — Crea una carpeta/asignatura nueva.\n"
        "- `!carpeta borrar <ruta>` — Borra una carpeta de la BdC (pide confirmación si tiene contenido).\n"
        "- `!carpeta listar` — Lista las carpetas existentes.\n"
        "- `!flashcard [tema:...] [tipo:...]` — Pregunta de repaso sobre un concepto.\n"
        "- `!ejercicio [enunciado] [tema:...] [tipo:...]` — Repaso con ejercicios o corrección del tuyo.\n"
        "- `!ejerciciostema <técnica/teorema>` — Busca ejercicios en la BdC que se resuelvan con esa técnica o teorema.\n"
        "- `!concepto [nombre] [tema:...] [tipo:...]` — Pide la definición de un concepto.\n"
        "- `!feynman [concepto] [tema:...] [tipo:...]` — Explícaselo con tus propias palabras.\n"
        "- `!repasartema [tema:...] [tipo:...]` — Te pregunta TODOS los conceptos de un tema uno a uno.\n"
        "- `!resumen` — Resumen de lo que has repasado en esta sesión.\n"
        "- `!mapa` — Qué conceptos dominas y cuáles tienes que repasar.\n"
        "- `!misestadisticas` — Tus métricas y aportaciones (curación) en la BdC.\n"
        "- `!trazabilidad [qa|interacciones|curacion|exportar]` — Consulta o descarga tu historial completo de aprendizaje y curación.\n"
        "- `!ayuda` — Esta lista de comandos.\n\n"
        "**Modificadores `tema:` y `tipo:`** (opcionales en comandos de estudio):\n"
        "- `tema:<carpeta o nombre>` — acota a esa subcarpeta o fichero.\n"
        "- `tipo:definicion|teorema|proposicion|formula|ejemplo|todo` — pide específicamente ese tipo de contenido.\n\n"
        "También puedes subir un PDF o una foto de tus apuntes manuscritos: se transcribirán "
        "automáticamente (OCR/multimodal) y te preguntaré dónde guardarlos en la BdC."
    )

    @command.new(name="ayuda", help="Lista todos los comandos disponibles")
    async def ayuda_handler(self, evt: MessageEvent) -> None:
        await evt.reply(self.AYUDA_TEXTO)