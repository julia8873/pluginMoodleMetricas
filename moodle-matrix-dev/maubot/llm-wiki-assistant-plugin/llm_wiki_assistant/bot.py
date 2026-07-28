# --8<-- [start:file_desc]
"""
Plugin de maubot para asistencia de estudio universitario con GitHub y Matrix.

Módulo principal: define la clase LlmWikiAssistant, la gestión de comandos de Matrix,
la organización de ficheros en carpetas de GitHub, y la coordinación de las
herramientas de estudio (flashcards, ejercicios, técnica Feynman, repaso de
temas, extracción de ejercicios por técnica y curación de base de conocimiento).
"""
# --8<-- [end:file_desc]


import asyncio
import base64
import re
import time
from datetime import datetime
from typing import Optional, Type

import aiohttp
# pyrefly: ignore [missing-import]
from maubot import Plugin, MessageEvent
# pyrefly: ignore [missing-import]
from maubot.handlers import command, event
# pyrefly: ignore [missing-import]
from mautrix.crypto.attachments import decrypt_attachment
# pyrefly: ignore [missing-import]
from mautrix.errors import DecryptionError
# pyrefly: ignore [missing-import]
from mautrix.types import EventType, MessageType, StateEvent
# pyrefly: ignore [missing-import]
from mautrix.util.async_db import UpgradeTable
# pyrefly: ignore [missing-import]
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
from .mixins.git_mixin import GitMixin
from .mixins.ocr_mixin import OcrMixin
from .mixins.cache_mixin import CacheMixin
from .mixins.locks_mixin import LocksMixin
from .mixins.utils_mixin import UtilsMixin
from .mixins.ingest_mixin import IngestMixin
from .mixins.comandos import ComandosMixin
from .sesiones import arrancar_tareas as _arrancar_tareas_sesiones
from .web_progreso import WebProgresoMixin


# --------------------------------------------------------------------
# Constantes de configuración
# --------------------------------------------------------------------
from .constants import (
    PENDIENTE_TTL_SEGUNDOS,
    CONFIRMACION_BORRADO_TTL_SEGUNDOS,
    SESION_VENTANA_SEGUNDOS,
    SESION_INACTIVIDAD_SEGUNDOS,
    SESION_DETECTOR_INTERVALO_SEGUNDOS,
    RETENTION_DAYS_DEFAULT,
    HISTORIAL_MAX_TURNOS,
    MAX_CONCEPTOS_REPASO_TEMA,
    MAX_CONCURRENCIA_GITHUB,
    FICHEROS_EXCLUIDOS_CONTEXTO,
    AGENTS_MD_PATH,
    OKF_LOG_PATH,
    PATRON_RENOMBRAR,
    PATRON_TEMA,
    PATRON_TIPO,
)


# --------------------------------------------------------------------
# Configuración del plugin
# --------------------------------------------------------------------

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        """Actualiza la configuración interna del plugin."""
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
        helper.copy("progress_api_token")            # Token Bearer para el endpoint /progreso
        helper.copy("retention_days")                # Días de retención de datos brutos de trazabilidad
        helper.copy("session_inactivity_seconds")    # Segundos de inactividad para cerrar sesión



# --------------------------------------------------------------------
# Clase principal LlmWikiAssistant
# --------------------------------------------------------------------

class LlmWikiAssistant(GitMixin, OcrMixin, CacheMixin, LocksMixin, UtilsMixin, IngestMixin, ComandosMixin, WebProgresoMixin, Plugin):

# --8<-- [start:start]

    async def start(self) -> None:
        """
        Punto de entrada de Maubot. Se ejecuta automáticamente al arrancar el plugin.
        Inicializa la configuración, las conexiones externas, la base de datos y
        todas las estructuras de estado en memoria necesarias para el funcionamiento.
        """
        # 1. Cargar configuración base del plugin definida por el usuario
        self.config.load_and_update()
        
        # 2. Inicializar clientes externos y base de datos

        self.tracker = Tracker(self.database)
        
        # 3. Inicializar diccionarios de estado en memoria para flujos asíncronos
        # Estos diccionarios mantienen el contexto de las interacciones en curso por usuario/sala
        self.pendientes = {}                 # Metadatos de archivos que esperan confirmación de subida
        self.lotes_subida = {}               # Agrupa múltiples archivos recibidos en ventana de tiempo
        self.tareas_lote = {}                # Referencias a tareas de fondo (asyncio) procesando lotes
        self.pendientes_destino = {}         # Estado cuando se pregunta la carpeta destino al usuario
        self.pendientes_borrado = {}         # Espera confirmación para borrar un archivo específico
        self.pendientes_borrado_carpeta = {} # Espera confirmación para borrar una carpeta entera
        self.pendientes_ocr = {}             # Confirmación para realizar OCR visual tras preview de PDF
        self.peticiones_llm = {}             # Referencias a tareas asíncronas de consultas LLM (para cancelarlas)
        self._historial_chat = {}            # (room_id, sender) -> list[{role, content}] — memoria de conversación

        # 4. Inicializar control de concurrencia
        # Locks por usuario/sala para evitar race conditions si llegan mensajes simultáneos
        self._user_locks = {}

        # 5. Inicializar cachés en memoria con TTL configurable
        # Optimizan el rendimiento evitando llamadas redundantes a la API de Git
        self._cache_docs = {}      # (owner, repo, filtro) -> (timestamp, contenido)
        self._cache_rutas = {}     # (owner, repo, path) -> (timestamp, lista_rutas)
        self._cache_carpetas = {}  # (owner, repo) -> (timestamp, lista_carpetas)
        self._cache_agents_md = {} # (owner, repo) -> (timestamp, contenido_agents_md)
        
        # Semáforo para limitar las peticiones simultáneas a GitHub/GitLab (prevenir rate-limits)
        self._semaforo_github = asyncio.Semaphore(MAX_CONCURRENCIA_GITHUB)

        # 6. Arrancar tareas periódicas: detector de inactividad de sesiones + job de purga
        self._tareas_sesiones = _arrancar_tareas_sesiones(self)
        
        # 7. Caché para mapeo de room_id a curso_id (State event es.ugr.gitmetrics.course_link)
        self._cache_course_id = {}
        # 8. Caché de fork_url de estudiantes (State event es.ugr.gitmetrics.student_fork)
        self._cache_fork_url = {}
        # 9. Caché de clientes Git por estudiante
        self._cache_git_clients = {}
        self._cache_git_configs = {}

    async def _config_para(self, student_id: str) -> dict:
        """Obtiene la config resuelta para un alumno con caché (TTL 30m)."""
        from .git_client import resolver_config_alumno
        ahora = time.time()
        ttl = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        if student_id in self._cache_git_configs:
            ts, cfg = self._cache_git_configs[student_id]
            if ahora - ts < ttl:
                return cfg
        cfg = await resolver_config_alumno(self.config, student_id, self.tracker)
        self._cache_git_configs[student_id] = (ahora, cfg)
        return cfg

    async def _git_para(self, student_id: str):
        """Devuelve el cliente Git instanciado dinámicamente para el alumno."""
        from .git_client import get_git_client
        ahora = time.time()
        ttl = (self.config["bdc_cache_ttl_minutos"] or 30) * 60
        if student_id in self._cache_git_clients:
            ts, client = self._cache_git_clients[student_id]
            if ahora - ts < ttl:
                return client
        cfg = await self._config_para(student_id)
        client = get_git_client(cfg)
        self._cache_git_clients[student_id] = (ahora, client)
        return client
# --8<-- [end:start]

    @event.on(EventType.ROOM_MESSAGE)
    async def track_student_course(self, evt: MessageEvent) -> None:
        """Resuelve el curso de la sala y registra/actualiza al estudiante."""
        if evt.sender == self.client.mxid:
            return

        room_id = evt.room_id
        if room_id not in self._cache_course_id:
            try:
                state = await self.client.get_state_event(room_id, "es.ugr.gitmetrics.course_link")
                if state and "course_id" in state:
                    self._cache_course_id[room_id] = int(state["course_id"])
                else:
                    self.log.warning(f"Sala {room_id} no tiene state event es.ugr.gitmetrics.course_link")
                    self._cache_course_id[room_id] = None
            except Exception as e:
                self.log.warning(f"Error o falta de state event course_link en {room_id}: {e}")
                self._cache_course_id[room_id] = None

        curso_id = self._cache_course_id[room_id]
        await self.tracker.ensure_estudiante(evt.sender, curso_id)

        if evt.sender not in self._cache_fork_url:
            try:
                states = await self.client.get_state(room_id)
                found = False
                for evt_state in states:
                    if evt_state.type == "es.ugr.gitmetrics.student_fork":
                        if evt_state.content and evt_state.content.get("matrix_user_id") == evt.sender:
                            fork_url = evt_state.content.get("fork_url")
                            self._cache_fork_url[evt.sender] = fork_url
                            await self.tracker.actualizar_repo_alumno(evt.sender, fork_url)
                            found = True
                            break
                
                if not found:
                    self._cache_fork_url[evt.sender] = False
            except Exception:
                self._cache_fork_url[evt.sender] = False

    @event.on(EventType.find("es.ugr.gitmetrics.student_fork", t_class=EventType.Class.STATE))
    async def handle_student_fork_event(self, evt: StateEvent) -> None:
        """Actualiza el repositorio del alumno al vuelo cuando Moodle aprovisiona el fork."""
        if evt.content and "fork_url" in evt.content and "matrix_user_id" in evt.content:
            fork_url = evt.content["fork_url"]
            mxid = evt.content["matrix_user_id"]
            self._cache_fork_url[mxid] = fork_url
            await self.tracker.actualizar_repo_alumno(mxid, fork_url)


# --8<-- [start:get_config_class]
    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        """Devuelve la clase de configuración asociada al plugin."""
        return Config
# --8<-- [end:get_config_class]

# --8<-- [start:get_db_upgrade_table]
    @classmethod
    def get_db_upgrade_table(cls) -> Optional[UpgradeTable]:
        """Devuelve la tabla de migraciones de base de datos."""
        return upgrade_table
# --8<-- [end:get_db_upgrade_table]

