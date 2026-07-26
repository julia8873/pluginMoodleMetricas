from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

from maubot.handlers import command
from maubot import MessageEvent

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

from .base import ComandosBaseMixin

class TrazabilidadMixin(ComandosBaseMixin):
# --8<-- [start:trazabilidad_handler]
    @command.new(name="trazabilidad", help="Consulta tu historial de aprendizaje y curación", require_subcommand=False)
    async def trazabilidad_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando de trazabilidad general."""
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
# --8<-- [end:trazabilidad_handler]

# --8<-- [start:trazabilidad_qa_handler]
    @trazabilidad_handler.subcommand("qa", help="Muestra el historial completo de preguntas, respuestas y evaluations")
    @command.argument("limite", pass_raw=True, required=False)
    async def trazabilidad_qa_handler(self, evt: MessageEvent, limite: str = "15") -> None:
        """Manejador del comando de trazabilidad de QA."""
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
# --8<-- [end:trazabilidad_qa_handler]

# --8<-- [start:trazabilidad_interacciones_handler]
    @trazabilidad_handler.subcommand("interacciones", help="Muestra el listado cronológico de interacciones con el bot")
    @command.argument("limite", pass_raw=True, required=False)
    async def trazabilidad_interacciones_handler(self, evt: MessageEvent, limite: str = "20") -> None:
        """Manejador del comando de trazabilidad de interacciones."""
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
# --8<-- [end:trazabilidad_interacciones_handler]

# --8<-- [start:trazabilidad_curacion_handler]
    @trazabilidad_handler.subcommand("curacion", help="Muestra el historial de subidas, movidos y borrados de la BdC")
    @command.argument("limite", pass_raw=True, required=False)
    async def trazabilidad_curacion_handler(self, evt: MessageEvent, limite: str = "20") -> None:
        """Manejador del comando de trazabilidad de curación."""
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
# --8<-- [end:trazabilidad_curacion_handler]

# --8<-- [start:trazabilidad_exportar_handler]
    @trazabilidad_handler.subcommand("exportar", help="Genera y envía un informe completo en Markdown de tu trazabilidad")
    async def trazabilidad_exportar_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando para exportar datos de trazabilidad."""
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
            self.log.warning(f"[llm_wiki_assistant] Error subiendo informe de trazabilidad: {exc}")
            await evt.reply("No pude adjuntar el archivo, envío el resumen aquí:\n\n" + "\n".join(lineas[:40]))
# --8<-- [end:trazabilidad_exportar_handler]
