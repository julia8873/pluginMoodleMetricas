from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any


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

class CacheMixin(_HostProtocol):
# --8<-- [start:invalidar_cache]
    def _invalidar_cache(self) -> None:
        """Invalida toda la caché en memoria tras operaciones de escritura en GitHub."""
        self._cache_docs.clear()
        self._cache_rutas.clear()
        self._cache_carpetas.clear()
        self._cache_agents_md.clear()
        self.log.info("[llm_wiki_assistant] Caché en memoria de la BdC invalidada.")
# --8<-- [end:invalidar_cache]

