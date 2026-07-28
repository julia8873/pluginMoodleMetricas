# --8<-- [start:file_desc]
"""
Endpoint HTTP nativo de Maubot para el panel del profesor.

Expone GET /progreso (relativo a self.webapp_url del plugin) y devuelve
el progreso de los alumnos en formato JSON, listo para que
block_gitmetrics lo consuma y cachee igual que las métricas de GitHub.

Autenticación: token Bearer definido en base-config.yaml (progress_api_token).
Requiere webapp: true en maubot.yaml.
"""
# --8<-- [end:file_desc]

import logging
from typing import TYPE_CHECKING, Any, Optional

from aiohttp.web import Request, Response, json_response

# pyrefly: ignore [missing-import]
from maubot.handlers import web

if TYPE_CHECKING:
    from .db import Tracker

log = logging.getLogger("maubot.llm_wiki_assistant.web_progreso")


# --8<-- [start:handler]
class WebProgresoMixin:
    """
    Mixin que añade el endpoint GET /progreso a LlmWikiAssistant.
    Se mezcla junto al resto de Mixins en la definición de la clase.
    """

    # Referencia tipada: se inyecta por la clase principal
    if TYPE_CHECKING:
        config: Any
        tracker: "Tracker"

    @web.get("/progreso")
    async def get_progreso(self, req: Request) -> Response:
        """
        GET /progreso?curso_id=<n>
        Authorization: Bearer <progress_api_token>

        Devuelve un array JSON con una fila por alumno:
          [
            {
              "id_pseudo":           "uuid",
              "curso_id":            42,
              "num_sesiones":        7,
              "ultima_sesion":       1753574400,
              "ultimo_resumen":      "El alumno repasó...",
              "conceptos_dominados": 12
            },
            ...
          ]

        Códigos de respuesta:
          200  Datos de progreso (array, puede estar vacío)
          401  Token ausente o inválido
          500  Error interno al consultar la BD
        """
        # -- 1. Autenticación con token Bearer --------------------------------
        token_esperado = self.config.get("progress_api_token", "")
        if not token_esperado:
            # Si no hay token configurado el endpoint está desactivado
            log.warning("[web_progreso] progress_api_token no configurado; acceso denegado")
            return Response(status=401, text="Endpoint desactivado: configura progress_api_token")

        auth_header = req.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(status=401, text="Authorization header requerido (Bearer token)")

        token_recibido = auth_header.removeprefix("Bearer ").strip()
        if token_recibido != token_esperado:
            log.warning("[web_progreso] Token incorrecto en petición desde %s", req.remote)
            return Response(status=401, text="Token inválido")

        # -- 2. Parámetro curso_id (opcional) ---------------------------------
        curso_id: Optional[int] = None
        raw = req.rel_url.query.get("curso_id", "")
        if raw:
            try:
                curso_id = int(raw)
            except ValueError:
                return Response(status=400, text="curso_id debe ser un entero")

        # -- 3. Consulta a la BD ----------------------------------------------
        try:
            filas = await self.tracker.obtener_progreso_para_moodle(curso_id)
        except Exception as exc:
            log.exception("[web_progreso] Error al obtener progreso para Moodle")
            return Response(status=500, text=f"Error interno: {exc}")

        # -- 4. Serializar: convertir tipos no-JSON (None, int de Postgres…) --
        resultado = []
        for fila in filas:
            resultado.append({
                "id_pseudo":           fila.get("id_pseudo"),
                "curso_id":            fila.get("curso_id"),
                "num_sesiones":        int(fila.get("num_sesiones") or 0),
                "ultima_sesion":       fila.get("ultima_sesion"),   # timestamp BIGINT o None
                "ultimo_resumen":      fila.get("ultimo_resumen"),  # texto o None
                "conceptos_dominados": int(fila.get("conceptos_dominados") or 0),
            })

        log.debug("[web_progreso] Devolviendo %d filas para curso_id=%s", len(resultado), curso_id)
        return json_response(resultado)
# --8<-- [end:handler]
