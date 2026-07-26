from __future__ import annotations
import asyncio
import base64
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

import aiohttp
from maubot.handlers import command, event
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

class LocksMixin(_HostProtocol):
# --8<-- [start:get_user_lock]
    def _get_user_lock(self, room_id: str, sender: str) -> asyncio.Lock:
        """Obtiene o crea el cerrojo de concurrencia para el estudiante en la sala."""
        clave = (room_id, sender)
        if clave not in self._user_locks:
            self._user_locks[clave] = asyncio.Lock()
        return self._user_locks[clave]
# --8<-- [end:get_user_lock]

