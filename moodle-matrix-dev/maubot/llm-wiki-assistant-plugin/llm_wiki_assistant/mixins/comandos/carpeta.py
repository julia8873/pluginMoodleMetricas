from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

import aiohttp
from maubot.handlers import command
from maubot import MessageEvent

from llm_wiki_assistant.db import Tracker
from llm_wiki_assistant.organizacion import sanitizar_carpeta
from llm_wiki_assistant.constants import CONFIRMACION_BORRADO_TTL_SEGUNDOS

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

class CarpetaMixin(ComandosBaseMixin):
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

                branch = self.config["default_branch"] or "main"
        carpeta = estado["carpeta"]
        ficheros = estado["ficheros"]

        await evt.reply(f"Borrando los {len(ficheros)} archivo(s) de la carpeta «{carpeta}», un momento...")

        errores = []
        for f in ficheros:
            try:
                await self._borrar_archivo_github(evt.sender, f["path"], f["sha"],
                    mensaje_commit=f"Borrar carpeta '{carpeta}': '{f['path']}' (por {evt.sender})",
                )
                await self.tracker.eliminar_fuentes_por_ruta(f["path"])
                await self.tracker.log_curacion(evt.sender, evt.room_id, "borrado", f["path"])
            except Exception as exc:
                self.log.warning(f"[llm_wiki_assistant] Error borrando '{f['path']}': {exc}")
                errores.append(f"{f['path']} ({exc})")

        self._invalidar_cache()
        if errores:
            await evt.reply(f"Se ha borrado parte de la carpeta «{carpeta}», pero hubo errores en {len(errores)} archivo(s):\n" + "\n".join(f"- {e}" for e in errores[:5]))
        else:
            await evt.reply(f"Carpeta «{carpeta}» y todos sus contenidos ({len(ficheros)} archivo(s)) borrados de la BdC.")
        await self.tracker.log_interaccion(evt.sender, evt.room_id, "carpeta_borrada", carpeta)
# --8<-- [end:procesar_confirmacion_borrado_carpeta]

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
                carpetas = await self._listar_carpetas(evt.sender)
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

                branch = self.config["default_branch"] or "main"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        await evt.reply(f"Revisando el contenido de la carpeta «{carpeta}» en la BdC...")
        async with aiohttp.ClientSession() as session:
            ficheros = await self._recorrer_carpeta_con_sha(session, evt.sender, carpeta)

        if not ficheros:
            await evt.reply(f"La carpeta «{carpeta}» no existe o ya está vacía en la BdC.")
            return

        ficheros_reales = [f for f in ficheros if not f["path"].endswith(".gitkeep")]

        if not ficheros_reales:
            await evt.reply(f"Borrando carpeta vacía «{carpeta}»...")
            for f in ficheros:
                try:
                    await self._borrar_archivo_github(evt.sender, f["path"], f["sha"],
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
            f"La carpeta «{carpeta}» **no está vacía**, contiene **{len(ficheros_reales)} archivo(s)**:\n{lista_muestra}{aviso_mas}\n\n"
            f"Vas a borrar la carpeta y **todo su contenido** de forma permanente. "
            f"Escribe `confirmar` en los próximos {CONFIRMACION_BORRADO_TTL_SEGUNDOS // 60} minutos para continuar, o ignora este mensaje para cancelar."
        )
# --8<-- [end:carpeta_borrar_handler]
