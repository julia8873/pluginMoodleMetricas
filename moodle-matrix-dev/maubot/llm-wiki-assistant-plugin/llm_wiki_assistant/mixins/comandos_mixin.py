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
from llm_wiki_assistant.constants import PENDIENTE_TTL_SEGUNDOS, CONFIRMACION_BORRADO_TTL_SEGUNDOS, MAX_CONCEPTOS_REPASO_TEMA, SESION_VENTANA_SEGUNDOS
from llm_wiki_assistant.helpers import _extraer_modificadores

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

class ComandosMixin(_HostProtocol):
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

# --8<-- [start:on_message]
    @event.on(EventType.ROOM_MESSAGE)
    async def on_message(self, evt: MessageEvent) -> None:
        """Manejador principal de eventos de mensaje. Procesa todos los mensajes entrantes de la sala."""
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
                self.log.warning(f"[llm_wiki_assistant] Error descifrando adjunto: {exc}")
                await evt.reply("He descargado el fichero pero no he podido descifrarlo. ¿Puedes reenviarlo?")
                return
            except Exception as exc:
                self.log.warning(f"[llm_wiki_assistant] Error descargando adjunto: {exc}")
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
                    self.log.error(f"[llm_wiki_assistant] Error al transcribir imagen «{nombre_archivo}»: {exc}")
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
# --8<-- [end:on_message]

# --8<-- [start:pregunta_handler]
    @command.new(
        name="pregunta",
        help="Pregunta sobre la documentación del repo: !pregunta [tema:<carpeta/fichero>] <texto>",
    )
    @command.argument("texto", pass_raw=True, required=True)
    async def pregunta_handler(self, evt: MessageEvent, texto: str) -> None:
        """Manejador del comando !pregunta para resolver dudas sobre los apuntes."""
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
# --8<-- [end:pregunta_handler]

# --8<-- [start:ficheros_handler]
    @command.new(name="ficheros", help="Lista los archivos .md/.txt encontrados en el repo de la BdC")
    async def ficheros_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !ficheros para listar los archivos del repositorio."""
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
# --8<-- [end:ficheros_handler]

# --8<-- [start:estadisticas_handler]
    @command.new(name="misestadisticas", help="Muestra tus métricas de trazabilidad en la BdC")
    async def estadisticas_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !estadisticas para mostrar estadísticas de estudio."""
        try:
            stats = await self.tracker.obtener_estadisticas(evt.sender)
        except Exception as exc:
            self.log.exception(f"[llm_wiki_assistant] Error consultando el tracker en !misestadisticas: {exc}")
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
# --8<-- [end:estadisticas_handler]

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

# --8<-- [start:documento_handler]
    @command.new(name="documento", help="Información de un documento concreto: !documento <nombre>")
    @command.argument("nombre", pass_raw=True, required=True)
    async def documento_handler(self, evt: MessageEvent, nombre: str) -> None:
        """Manejador del comando !documento para obtener información de un archivo."""
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
            self.log.exception(f"[llm_wiki_assistant] Error consultando el tracker en !documento: {exc}")
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
# --8<-- [end:documento_handler]

# --8<-- [start:borrar_handler]
    @command.new(name="borrar", help="Borra un documento de la BdC (pide confirmación): !borrar <nombre>")
    @command.argument("nombre", pass_raw=True, required=True)
    async def borrar_handler(self, evt: MessageEvent, nombre: str) -> None:
        """Manejador del comando !borrar para eliminar un archivo."""
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
# --8<-- [end:borrar_handler]

# --8<-- [start:procesar_confirmacion_borrado]
    async def _procesar_confirmacion_borrado(self, evt: MessageEvent, estado: dict) -> None:
        """Procesa la confirmación del usuario para borrar un archivo."""
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
            self.log.warning(f"[llm_wiki_assistant] Error borrando '{ruta}' de GitHub: {exc}")
            await evt.reply(f"No he podido borrar «{ruta}»: {exc}")
            return

        await self.tracker.eliminar_fuentes_por_ruta(ruta)
        await evt.reply(f"«{ruta}» borrado de la BdC.")
        # T3: Registro en curaciones
        await self.tracker.log_curacion(evt.sender, evt.room_id, "borrado", ruta)
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "documento_borrado", ruta)
# --8<-- [end:procesar_confirmacion_borrado]

# --8<-- [start:procesar_confirmacion_borrado_carpeta]
    async def _procesar_confirmacion_borrado_carpeta(self, evt: MessageEvent, estado: dict) -> None:
        """Procesa la confirmación del usuario para borrar una carpeta completa."""
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
                self.log.warning(f"[llm_wiki_assistant] Error borrando '{f['path']}': {exc}")
                errores.append(f"{f['path']} ({exc})")

        self._invalidar_cache()
        if errores:
            await evt.reply(f"⚠️ Se ha borrado parte de la carpeta «{carpeta}», pero hubo errores en {len(errores)} archivo(s):\n" + "\n".join(f"- {e}" for e in errores[:5]))
        else:
            await evt.reply(f"Carpeta «{carpeta}» y todos sus contenidos ({len(ficheros)} archivo(s)) borrados de la BdC.")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "carpeta_borrada", carpeta)
# --8<-- [end:procesar_confirmacion_borrado_carpeta]

# --8<-- [start:mover_handler]
    @command.new(name="mover", help="Mueve un documento de carpeta: !mover <nombre> -> <carpeta_destino|raiz>")
    @command.argument("texto", pass_raw=True, required=True)
    async def mover_handler(self, evt: MessageEvent, texto: str) -> None:
        """Manejador del comando !mover para cambiar la ubicación de un archivo."""
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
            self.log.warning(f"[llm_wiki_assistant] Error moviendo '{ruta_antigua}' -> '{ruta_nueva}': {exc}")
            await evt.reply(f"No he podido mover «{ruta_antigua}»: {exc}")
            return

        await self.tracker.actualizar_ruta_fuente(ruta_antigua, ruta_nueva)
        await evt.reply(f"«{ruta_antigua}» movido a `{ruta_nueva}`.")
        # T3: Registro en curaciones
        await self.tracker.log_curacion(evt.sender, evt.room_id, "movido", f"{ruta_antigua} -> {ruta_nueva}")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "documento_movido", f"{ruta_antigua} -> {ruta_nueva}")
# --8<-- [end:mover_handler]

# --8<-- [start:carpeta_handler]
    @command.new(name="carpeta", help="Gestiona las carpetas/asignaturas de la BdC", require_subcommand=False)
    async def carpeta_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !carpeta para gestionar carpetas."""
        await evt.reply("Usa `!carpeta crear <ruta>`, `!carpeta borrar <ruta>` o `!carpeta listar`.")
# --8<-- [end:carpeta_handler]

# --8<-- [start:carpeta_crear_handler]
    @carpeta_handler.subcommand("crear", help="Crea una carpeta nueva: !carpeta crear <ruta>")
    @command.argument("ruta", pass_raw=True, required=True)
    async def carpeta_crear_handler(self, evt: MessageEvent, ruta: str) -> None:
        """Manejador del comando para crear una nueva carpeta."""
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
            self.log.warning(f"[llm_wiki_assistant] Error creando carpeta: {exc}")
            await evt.reply(f"No he podido crear la carpeta «{carpeta}».")
            return

        await evt.reply(f"Carpeta «{carpeta}» creada.")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "carpeta_creada", carpeta)
# --8<-- [end:carpeta_crear_handler]

# --8<-- [start:carpeta_listar_handler]
    @carpeta_handler.subcommand("listar", help="Lista las carpetas existentes en la BdC")
    async def carpeta_listar_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando para listar carpetas."""
        owner = self.config["default_owner"]
        repo = self.config["default_repo"]
        token = self._obtener_git_token()

        carpetas = await self._listar_carpetas(owner, repo, token)
        if not carpetas:
            await evt.reply("Todavía no hay carpetas creadas. Usa `!carpeta crear <nombre>`.")
            return

        await evt.reply("Carpetas en la BdC:\n" + "\n".join(f"- {c}" for c in carpetas))
# --8<-- [end:carpeta_listar_handler]

# --8<-- [start:carpeta_borrar_handler]
    @carpeta_handler.subcommand("borrar", help="Borra una carpeta de la BdC: !carpeta borrar <ruta>")
    @command.argument("ruta", pass_raw=True, required=True)
    async def carpeta_borrar_handler(self, evt: MessageEvent, ruta: str) -> None:
        """Manejador del comando para borrar una carpeta."""
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
                    self.log.warning(f"[llm_wiki_assistant] Error borrando {f['path']}: {exc}")
            self._invalidar_cache()
            await evt.reply(f"Carpeta vacía «{carpeta}» eliminada de la BdC.")
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
# --8<-- [end:carpeta_borrar_handler]

# --8<-- [start:plantear_pregunta]
    async def _plantear_pregunta(
        self, evt: MessageEvent, tipo: str, generador, tema: str = "", tipo_contenido: str = ""
    ) -> None:
        """Plantea una pregunta de estudio al usuario."""
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
# --8<-- [end:plantear_pregunta]

# --8<-- [start:evaluar_pendiente]
    async def _evaluar_pendiente(self, evt: MessageEvent, pendiente: dict) -> None:
        """Evalúa una respuesta pendiente de una pregunta anterior."""
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
            self.log.warning(f"[llm_wiki_assistant] Error del LLM corrigiendo la respuesta: {exc}")
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
# --8<-- [end:evaluar_pendiente]

# --8<-- [start:avanzar_repaso_tema]
    async def _avanzar_repaso_tema(self, evt: MessageEvent, pendiente: dict, acierto: bool) -> None:
        """Avanza a la siguiente pregunta en el repaso de un tema."""
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
# --8<-- [end:avanzar_repaso_tema]

# --8<-- [start:flashcard_handler]
    @command.new(
        name="flashcard",
        help="Pregunta de repaso sobre un concepto: !flashcard [tema:<...>] [tipo:<...>]",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def flashcard_handler(self, evt: MessageEvent, texto: str = "") -> None:
        """Manejador del comando !flashcard para practicar conceptos."""
        _, tema, tipo_contenido = _extraer_modificadores(texto)
        await self._plantear_pregunta(
            evt, tipo="flashcard", generador=generar_flashcard, tema=tema, tipo_contenido=tipo_contenido
        )
# --8<-- [end:flashcard_handler]

# --8<-- [start:ejercicio_handler]
    @command.new(
        name="ejercicio",
        help="Repaso con ejercicios: !ejercicio [tema:<...>] [tipo:<...>] o !ejercicio <tu ejercicio/solución>",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def ejercicio_handler(self, evt: MessageEvent, texto: str = "") -> None:
        """Manejador del comando !ejercicio para generar ejercicios prácticos."""
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
# --8<-- [end:ejercicio_handler]

# --8<-- [start:concepto_handler]
    @command.new(
        name="concepto",
        help="Pregunta la definición de un concepto: !concepto [nombre] [tema:<...>] [tipo:<...>]",
    )
    @command.argument("nombre", pass_raw=True, required=False)
    async def concepto_handler(self, evt: MessageEvent, nombre: str = "") -> None:
        """Manejador del comando !concepto para explicar un concepto específico."""
        await self._plantear_pregunta_concepto(
            evt, tipo="concepto", nombre=nombre,
            plantilla_pregunta="¿Cuál es la definición de «{concepto}»?",
        )
# --8<-- [end:concepto_handler]

# --8<-- [start:feynman_handler]
    @command.new(
        name="feynman",
        help="Técnica Feynman (explícamelo con tus palabras): !feynman [concepto] [tema:<...>] [tipo:<...>]",
    )
    @command.argument("nombre", pass_raw=True, required=False)
    async def feynman_handler(self, evt: MessageEvent, nombre: str = "") -> None:
        """Manejador del comando !feynman para practicar la Técnica de Feynman."""
        await self._plantear_pregunta_concepto(
            evt, tipo="feynman", nombre=nombre,
            plantilla_pregunta="Explícame con tus propias palabras qué es «{concepto}» (sin copiarlo de los apuntes).",
        )
# --8<-- [end:feynman_handler]

# --8<-- [start:plantear_pregunta_concepto]
    async def _plantear_pregunta_concepto(
        self, evt: MessageEvent, tipo: str, nombre: str, plantilla_pregunta: str
    ) -> None:
        """Plantea una pregunta específica sobre un concepto."""
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
# --8<-- [end:plantear_pregunta_concepto]

# --8<-- [start:repasartema_handler]
    @command.new(
        name="repasartema",
        help="Repasa TODOS los conceptos de un tema, uno a uno: !repasartema [tema:<...>] [tipo:<...>]",
    )
    @command.argument("texto", pass_raw=True, required=False)
    async def repasartema_handler(self, evt: MessageEvent, texto: str = "") -> None:
        """Manejador del comando !repasartema para estudiar un tema completo."""
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
            self.log.warning(f"[llm_wiki_assistant] Error listando conceptos en !repasartema: {exc}")
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
            self.log.warning(f"[llm_wiki_assistant] Error generando lote de preguntas: {exc}")
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
# --8<-- [end:repasartema_handler]

    # --8<-- [start:ejerciciostema_handler]
    @command.new(
        name="ejerciciostema",
        help="Busca ejercicios o problemas en la BdC que apliquen una técnica/teorema: !ejerciciostema <técnica>",
    )
    @command.argument("tecnica", pass_raw=True, required=True)
    async def ejerciciostema_handler(self, evt: MessageEvent, tecnica: str) -> None:
        """Manejador del comando !ejerciciostema para ejercicios de un tema."""
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
            self.log.warning(f"[llm_wiki_assistant] Error buscando ejercicios por técnica: {exc}")
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
    # --8<-- [end:ejerciciostema_handler]

# --8<-- [start:resumen_handler]
    @command.new(name="resumen", help="Resumen de lo que has repasado en esta sesión")
    async def resumen_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !resumen para generar un resumen de los apuntes."""
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
# --8<-- [end:resumen_handler]

# --8<-- [start:mapa_handler]
    @command.new(name="mapa", help="Qué conceptos dominas y cuáles tienes que repasar")
    async def mapa_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !mapa para generar un mapa conceptual."""
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
# --8<-- [end:mapa_handler]

# --8<-- [start:ayuda_handler]
    @command.new(name="ayuda", help="Lista todos los comandos disponibles")
    async def ayuda_handler(self, evt: MessageEvent) -> None:
        """Manejador del comando !ayuda para mostrar los comandos disponibles."""
        await evt.reply(self.AYUDA_TEXTO)
# --8<-- [end:ayuda_handler]

