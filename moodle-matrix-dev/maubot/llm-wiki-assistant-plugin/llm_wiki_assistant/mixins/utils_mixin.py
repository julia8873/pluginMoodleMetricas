from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Optional, Any

from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.latex_render import procesar_texto_con_latex
from llm_wiki_assistant.llm_provider import LLMProvider

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

class UtilsMixin(_HostProtocol):
# --8<-- [start:crear_llm]
    def _crear_llm(self) -> LLMProvider:
        """Crea e inicializa la instancia del modelo de lenguaje."""
        return LLMProvider(self.config["llm_base_url"], self.config["llm_api_key"], self.config["llm_model"])
# --8<-- [end:crear_llm]

# --8<-- [start:crear_llm_vision]
    def _crear_llm_vision(self) -> LLMProvider:
        """Crea e inicializa la instancia del modelo de lenguaje con capacidades de visión."""
        base_url = self.config["llm_vision_base_url"] or self.config["llm_base_url"]
        api_key = self.config["llm_vision_api_key"] or self.config["llm_api_key"]
        modelo_vision = self.config["llm_vision_model"] or self.config["llm_model"]
        return LLMProvider(base_url, api_key, modelo_vision)
# --8<-- [end:crear_llm_vision]

# --8<-- [start:responder_con_latex]
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
                self.log.warning(f"[llm_wiki_assistant] Error subiendo fórmula LaTeX renderizada: {exc}")
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
# --8<-- [end:responder_con_latex]

