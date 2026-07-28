from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.estudio import (
    EstudioError, elegir_concepto, evaluar_respuesta
)
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
        client: Any
        database: Any
        
        async def _procesar_confirmacion_ocr(self, evt: MessageEvent, estado: dict) -> None: ...
        async def _procesar_confirmacion_borrado(self, evt: MessageEvent, estado: dict) -> None: ...
        async def _procesar_confirmacion_borrado_carpeta(self, evt: MessageEvent, estado: dict) -> None: ...
        async def _procesar_respuesta_destino(self, evt: MessageEvent, estado: dict) -> None: ...
        async def _evaluar_pendiente(self, evt: MessageEvent, pendiente: dict) -> None: ...
else:
    _HostProtocol = object

class ComandosBaseMixin(_HostProtocol):
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

# --8<-- [start:plantear_pregunta]
    async def _plantear_pregunta(
        self, evt: MessageEvent, tipo: str, generador, tema: str = "", tipo_contenido: str = ""
    ) -> None:
        """Plantea una pregunta de estudio al usuario."""
        owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
        clave = (evt.room_id, evt.sender)
        self.peticiones_llm[clave] = asyncio.current_task()
        try:
            contenido_docs = await self._obtener_documentacion(owner, repo, token, tema)
            if not contenido_docs and tema:
                await evt.reply(f"No he encontrado ningún fichero en la BdC que coincida con «{tema}».")
                return
            if not contenido_docs:
                await evt.reply("No he podido leer la documentación del repositorio.")
                return

            generada = await generador(contenido_docs, self._crear_llm(), tipo_contenido)
        except asyncio.CancelledError:
            self.log.info(f"Consulta LLM cancelada para {clave}")
            return
        except Exception as exc:
            await evt.reply(f"No he podido generar la pregunta: {exc}")
            return
        finally:
            self.peticiones_llm.pop(clave, None)

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
        self.peticiones_llm[clave] = asyncio.current_task()
        try:
            contenido_docs = pendiente.get("contenido_docs")
            if contenido_docs is None:
                owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
                contenido_docs = await self._obtener_documentacion(owner, repo, token, pendiente.get("tema", ""))

            resultado = await evaluar_respuesta(
                pendiente["tipo"], pendiente["concepto"], pendiente["pregunta"],
                evt.content.body, contenido_docs, self._crear_llm(),
            )
        except asyncio.CancelledError:
            self.log.info(f"Corrección LLM cancelada para {clave}")
            self.pendientes[clave] = pendiente
            return
        except EstudioError as exc:
            self.pendientes[clave] = pendiente
            await evt.reply(f"No he podido corregir la respuesta: {exc}")
            return
        except Exception as exc:
            self.pendientes[clave] = pendiente
            self.log.warning(f"[llm_wiki_assistant] Error del LLM corrigiendo la respuesta: {exc}")
            await evt.reply(f"No he podido corregir tu respuesta: {exc}\nTu pregunta sigue pendiente.")
            return
        finally:
            self.peticiones_llm.pop(clave, None)

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

# --8<-- [start:plantear_pregunta_concepto]
    async def _plantear_pregunta_concepto(
        self, evt: MessageEvent, tipo: str, nombre: str, plantilla_pregunta: str
    ) -> None:
        """Plantea una pregunta específica sobre un concepto."""
        concepto, tema, tipo_contenido = _extraer_modificadores(nombre)

        owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
        clave = (evt.room_id, evt.sender)
        self.peticiones_llm[clave] = asyncio.current_task()
        try:
            contenido_docs = await self._obtener_documentacion(owner, repo, token, tema)
            if not contenido_docs and tema:
                await evt.reply(f"No he encontrado ningún fichero de la BdC que coincida con «{tema}».")
                return
            if not contenido_docs:
                await evt.reply("No he podido leer la documentación del repositorio.")
                return

            if not concepto:
                concepto = await elegir_concepto(contenido_docs, self._crear_llm(), tipo_contenido)
        except asyncio.CancelledError:
            self.log.info(f"Selección de concepto LLM cancelada para {clave}")
            return
        except Exception as exc:
            await evt.reply(f"No he podido elegir un concepto: {exc}")
            return
        finally:
            self.peticiones_llm.pop(clave, None)

        pregunta = plantilla_pregunta.format(concepto=concepto)
        self.pendientes[(evt.room_id, evt.sender)] = {
            "tipo": tipo, "concepto": concepto, "pregunta": pregunta, "timestamp": int(time.time()),
            "contenido_docs": contenido_docs,
            "tema": tema,
        }
        await self._responder_con_latex(evt, pregunta)
# --8<-- [end:plantear_pregunta_concepto]
