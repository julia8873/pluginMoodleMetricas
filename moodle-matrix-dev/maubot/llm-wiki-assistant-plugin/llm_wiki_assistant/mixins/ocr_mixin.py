from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

from maubot import MessageEvent
from mautrix.crypto.attachments import decrypt_attachment

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.image_ocr import OcrError, transcribir_pdf_escaneado
from llm_wiki_assistant.organizacion import VENTANA_LOTE_SEGUNDOS, es_respuesta_modo_lote, formatear_lista_carpetas, resolver_eleccion_carpeta
from llm_wiki_assistant.constants import PENDIENTE_TTL_SEGUNDOS, PATRON_RENOMBRAR

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

class OcrMixin(_HostProtocol):
# --8<-- [start:procesar_confirmacion_ocr]
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
                    await evt.reply(f"Procesando OCR visual... (página {pag_actual}/{total_pags})")

                texto_extraido, paginas_fallidas = await transcribir_pdf_escaneado(
                    contenido_binario, llm_vision, progress_callback=notificar_progreso
                )
                if paginas_fallidas:
                    self.log.warning(f"[llm_wiki_assistant] Páginas con error al transcribir PDF: {paginas_fallidas}")
                    await evt.reply(f"Aviso: Hubo problemas al transcribir {len(paginas_fallidas)} página(s).")
                tipo_interaccion = "pdf_escaneado_ocr"
            except (OcrError, Exception) as exc:
                self.log.error(f"[llm_wiki_assistant] Error en OCR visual de «{nombre_archivo}»: {exc}")
                await evt.reply(
                    f"Error al procesar «{nombre_archivo}» con OCR visual: {exc}\n\n"
                    "Si el error persiste, verifica la clave API/configuración del LLM en base-config.yaml o responde **no** al subir el archivo para guardar el texto extraído sin OCR visual."
                )
                return
        else:
            await evt.reply(f"De acuerdo, usaré el texto extraido directamente para «{nombre_archivo}».")
            tipo_interaccion = "pdf_subido"

        await self._encolar_para_lote(evt, nombre_archivo, texto_extraido, tipo_interaccion)
# --8<-- [end:procesar_confirmacion_ocr]

# --8<-- [start:encolar_para_lote]
    async def _encolar_para_lote(
        self, evt: MessageEvent, nombre_archivo: str, texto_extraido: str, tipo_interaccion: str
    ) -> None:
        """Encola un archivo para ser procesado posteriormente en lote."""
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
# --8<-- [end:encolar_para_lote]

# --8<-- [start:vista_previa_transcripcion]
    @staticmethod
    def _vista_previa_transcripcion(texto: str, longitud: int = 350) -> str:
        """Genera una vista previa de la transcripción de un documento."""
        vista = (texto or "").strip()
        if len(vista) > longitud:
            vista = vista[:longitud] + "..."
        return vista
# --8<-- [end:vista_previa_transcripcion]

# --8<-- [start:debounce_lote]
    async def _debounce_lote(self, room_id, sender) -> None:
        """Implementa un mecanismo de debounce para el procesamiento por lotes."""
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

                if len(ficheros) == 1:
                    carpetas = await self._listar_carpetas(evt.sender)
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
            self.log.error(f"[llm_wiki_assistant] Error en _debounce_lote para {room_id}: {exc}")
            try:
                await self.client.send_text(
                    room_id,
                    f"Error al preparar el guardado del fichero en el repositorio: {exc}\n"
                    "Por favor, intenta subir el archivo nuevamente o verifica la configuración del repositorio."
                )
            except Exception:
                pass
# --8<-- [end:debounce_lote]

# --8<-- [start:procesar_respuesta_destino]
    async def _procesar_respuesta_destino(self, evt: MessageEvent, estado: dict) -> None:
        """Procesa la respuesta del usuario sobre la carpeta de destino de un archivo."""
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

            carpetas = await self._listar_carpetas(evt.sender)
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
# --8<-- [end:procesar_respuesta_destino]

# --8<-- [start:procesar_renombrado]
    async def _procesar_renombrado(self, evt: MessageEvent, estado: dict, nuevo_nombre: str) -> None:
        """Procesa la respuesta del usuario para renombrar un archivo."""
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
# --8<-- [end:procesar_renombrado]

# --8<-- [start:descargar_adjunto]
    async def _descargar_adjunto(self, evt: MessageEvent) -> bytes:
        """Descarga un archivo adjunto enviado a la sala de Matrix."""
        if evt.content.file is not None:
            contenido_cifrado = await self.client.download_media(evt.content.file.url)
            return decrypt_attachment(
                contenido_cifrado,
                evt.content.file.key.key,
                evt.content.file.hashes["sha256"],
                evt.content.file.iv,
            )
        return await self.client.download_media(evt.content.url)
# --8<-- [end:descargar_adjunto]

