from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

from maubot.handlers import event
from maubot import MessageEvent
from mautrix.errors import DecryptionError
from mautrix.types import EventType, MessageType

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.image_ocr import OcrError, es_imagen_de_apuntes, transcribir_imagen
from llm_wiki_assistant.pdf_ingest import PdfExtractionError, extraer_texto_pdf, parece_texto_de_baja_calidad
from llm_wiki_assistant.constants import PENDIENTE_TTL_SEGUNDOS, HISTORIAL_MAX_TURNOS
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
        _historial_chat: dict
        client: Any
        database: Any
else:
    _HostProtocol = object

from .base import ComandosBaseMixin

class MensajesMixin(ComandosBaseMixin):
# --8<-- [start:on_message]
    @event.on(EventType.ROOM_MESSAGE)
    async def on_message(self, evt: MessageEvent) -> None:
        """Manejador principal de eventos de mensaje. Procesa todos los mensajes entrantes de la sala."""
        if evt.sender == self.client.mxid:
            return

        clave = (evt.room_id, evt.sender)
        lock = self._get_user_lock(evt.room_id, evt.sender)

        # Protegemos la evaluación del mensaje y acceso al estado con lock
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

                # Tratar cualquier mensaje sin exclamacion como una pregunta a la BdC
                texto_msg = evt.content.body
                texto, tema, _ = _extraer_modificadores(texto_msg)
                provider = self._crear_llm()

                try:
                    # Preguntar al LLM si este mensaje justifica leer la Base de Conocimiento
                    necesita_bdc = await provider.evaluar_necesidad_bdc(texto_msg)
                except RuntimeError as exc:
                    await evt.reply(f"Error de conexión con la IA: {exc}")
                    return

                if clave not in self._historial_chat:
                    # Restaurar desde BD si la memoria está vacía (reinicio o nueva sesión)
                    h_restaurado = await self.tracker.obtener_historial_conversacion(evt.sender, evt.room_id, limit=HISTORIAL_MAX_TURNOS)
                    ultimo_resumen = await self.tracker.obtener_ultimo_resumen_sesion_alumno(evt.sender)
                    if ultimo_resumen:
                        # Inyectar el resumen de la última sesión como contexto extra inicial
                        h_restaurado.insert(0, {
                            "role": "system",
                            "content": f"Contexto pasivo de la última sesión (uso interno, no mencionar al usuario a menos que pregunte):\n{ultimo_resumen}"
                        })
                    self._historial_chat[clave] = h_restaurado

                historial = self._historial_chat[clave]

                if not necesita_bdc:
                    respuesta = await provider.conversar(texto_msg, historial=historial)
                    historial.append({"role": "user", "content": texto_msg})
                    historial.append({"role": "assistant", "content": respuesta})
                    if len(historial) > HISTORIAL_MAX_TURNOS:
                        self._historial_chat[clave] = historial[-HISTORIAL_MAX_TURNOS:]
                    await self._responder_con_latex(evt, respuesta)
                    
                    # Guardamos la charla también en BD para no perderla si el bot se reinicia
                    await self.tracker.log_qa(evt.sender, evt.room_id, "conversacion", texto_msg, respuesta, "informativo")
                    return
                
                token = self._obtener_git_token()
                owner = self.config["default_owner"]
                repo = self.config["default_repo"]
                
                await evt.reply("Consultando la Base de Conocimiento, un momento...")
                
                self.peticiones_llm[clave] = asyncio.current_task()
                try:
                    contenido_docs = await self._obtener_documentacion(owner, repo, token, tema)
                    if not contenido_docs and tema:
                        await evt.reply(f"No he encontrado ningún fichero de la BdC que coincida con «{tema}».")
                        return
                    if not contenido_docs:
                        await evt.reply("No he podido leer la documentación del repositorio.")
                        return
                    
                    respuesta = await provider.preguntar(texto, contenido_docs, historial=historial)
                except asyncio.CancelledError:
                    self.log.info(f"Consulta LLM cancelada para {clave}")
                    return
                except Exception as exc:
                    await evt.reply(f"Error al consultar el modelo: {exc}")
                    return
                finally:
                    self.peticiones_llm.pop(clave, None)
                    
                historial.append({"role": "user", "content": texto})
                historial.append({"role": "assistant", "content": respuesta})
                if len(historial) > HISTORIAL_MAX_TURNOS:
                    self._historial_chat[clave] = historial[-HISTORIAL_MAX_TURNOS:]
                    
                await self._responder_con_latex(evt, respuesta)
                await self.tracker.log_interaccion(evt.sender, evt.room_id, "pregunta_implicita", texto)
                await self.tracker.log_qa(evt.sender, evt.room_id, "pregunta_implicita", texto, respuesta, "informativo")
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
                        f"Error al transcribir «{nombre_archivo}»: {exc}\n\n"
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
