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
from mautrix.types import EventType, MessageType
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
        self.git = get_git_client(self.config)
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
# --8<-- [end:start]


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

