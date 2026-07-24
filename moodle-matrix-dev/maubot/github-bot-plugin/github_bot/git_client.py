import asyncio
import base64
import time
import urllib.parse
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Tuple, Any
import aiohttp

FICHEROS_EXCLUIDOS_CONTEXTO = {"log.md", "readme.md", "welcome.md", "agents.md"}
OKF_LOG_PATH = "okf/log.md"

class GitProvider(ABC):
    """Interfaz modular para operaciones sobre repositorios Git (GitHub / GitLab)."""

    @abstractmethod
    async def obtener_documentacion(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        filtro: str, cache_docs: dict, ttl_segundos: int, semaforo: asyncio.Semaphore, log: Any
    ) -> str:
        pass

    @abstractmethod
    async def listar_rutas(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, cache_rutas: dict, ttl_segundos: int, semaforo: asyncio.Semaphore
    ) -> List[str]:
        pass

    @abstractmethod
    async def listar_carpetas(
        self, owner: str, repo: str, token: str, cache_carpetas: dict, 
        ttl_segundos: int, semaforo: asyncio.Semaphore
    ) -> List[str]:
        pass

    @abstractmethod
    async def obtener_info_y_contenido(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def subir_archivo(
        self, owner: str, repo: str, token: str, path: str, contenido: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        pass

    @abstractmethod
    async def subir_o_actualizar_archivo(
        self, owner: str, repo: str, token: str, path: str, contenido: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> bool:
        pass

    @abstractmethod
    async def append_log_okf(
        self, owner: str, repo: str, token: str, branch: str, entrada: str, 
        mensaje_commit: str, semaforo: asyncio.Semaphore
    ) -> None:
        pass

    @abstractmethod
    async def borrar_archivo(
        self, owner: str, repo: str, token: str, path: str, branch: str, 
        mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        pass

    @abstractmethod
    async def mover_archivo(
        self, owner: str, repo: str, token: str, old_path: str, new_path: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        pass

    @abstractmethod
    async def obtener_historial_fichero(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def recorrer_carpeta_con_sha(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> List[Dict[str, Any]]:
        pass


class GitHubClient(GitProvider):
    """Implementación del proveedor Git para la API REST de GitHub."""

    def _headers(self, token: str) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    async def obtener_documentacion(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        filtro: str, cache_docs: dict, ttl_segundos: int, semaforo: asyncio.Semaphore, log: Any
    ) -> str:
        ahora = time.time()
        clave_cache = (owner, repo, filtro.lower())
        if clave_cache in cache_docs:
            ts_guardado, contenido_cached = cache_docs[clave_cache]
            if ahora - ts_guardado < ttl_segundos:
                if log:
                    log.info(f"[github_bot] Usando caché en memoria para documentación (filtro: '{filtro}')")
                return contenido_cached

        headers = self._headers(token)
        textos = await self._recorrer_carpeta_docs(session, owner, repo, headers, "", filtro, semaforo, log)
        contenido_total = "\n\n".join(textos)
        cache_docs[clave_cache] = (ahora, contenido_total)
        return contenido_total

    async def _recorrer_carpeta_docs(
        self, session: aiohttp.ClientSession, owner: str, repo: str, headers: dict, 
        path: str, filtro: str, semaforo: asyncio.Semaphore, log: Any
    ) -> List[str]:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        textos = []
        async with semaforo:
            if log:
                log.info(f"[github_bot] Consultando GitHub: {url}")
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return textos
                elementos = await resp.json()

        dir_tasks, file_tasks = [], []
        for elem in elementos:
            if elem["type"] == "dir":
                dir_tasks.append(self._recorrer_carpeta_docs(session, owner, repo, headers, elem["path"], filtro, semaforo, log))
            elif elem["type"] == "file" and elem["name"].endswith((".md", ".txt")):
                if elem["name"].lower() in FICHEROS_EXCLUIDOS_CONTEXTO:
                    continue
                if filtro and filtro.lower() not in elem["path"].lower():
                    continue
                file_tasks.append(self._descargar_fichero(session, elem["path"], elem["download_url"], headers, semaforo, log))

        if dir_tasks or file_tasks:
            resultados = await asyncio.gather(*(dir_tasks + file_tasks), return_exceptions=True)
            for res in resultados:
                if isinstance(res, list):
                    textos.extend(res)
                elif isinstance(res, str) and res.strip():
                    textos.append(res)
        return textos

    async def _descargar_fichero(
        self, session: aiohttp.ClientSession, path: str, download_url: str, 
        headers: dict, semaforo: asyncio.Semaphore, log: Any
    ) -> str:
        async with semaforo:
            if log:
                log.info(f"[github_bot] Descargando archivo GitHub: {path}")
            async with session.get(download_url, headers=headers) as resp:
                if resp.status == 200:
                    contenido = await resp.text()
                    return f"## Archivo: {path}\n{contenido}"
        return ""

    async def listar_rutas(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, cache_rutas: dict, ttl_segundos: int, semaforo: asyncio.Semaphore
    ) -> List[str]:
        ahora = time.time()
        clave_cache = (owner, repo, path)
        if clave_cache in cache_rutas:
            ts_guardado, rutas_cached = cache_rutas[clave_cache]
            if ahora - ts_guardado < ttl_segundos:
                return list(rutas_cached)

        headers = self._headers(token)
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        rutas = []
        async with semaforo:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return rutas
                elementos = await resp.json()

        sub_tasks = []
        for elem in elementos:
            if elem["type"] == "dir":
                sub_tasks.append(self.listar_rutas(session, owner, repo, token, elem["path"], cache_rutas, ttl_segundos, semaforo))
            elif elem["type"] == "file" and elem["name"].endswith((".md", ".txt")):
                rutas.append(elem["path"])

        if sub_tasks:
            resultados = await asyncio.gather(*sub_tasks, return_exceptions=True)
            for res in resultados:
                if isinstance(res, list):
                    rutas.extend(res)

        cache_rutas[clave_cache] = (ahora, list(rutas))
        return rutas

    async def listar_carpetas(
        self, owner: str, repo: str, token: str, cache_carpetas: dict, 
        ttl_segundos: int, semaforo: asyncio.Semaphore
    ) -> List[str]:
        ahora = time.time()
        clave_cache = (owner, repo)
        if clave_cache in cache_carpetas:
            ts_guardado, carpetas_cached = cache_carpetas[clave_cache]
            if ahora - ts_guardado < ttl_segundos:
                return list(carpetas_cached)

        headers = self._headers(token)
        carpetas: List[str] = []
        async with aiohttp.ClientSession() as session:
            await self._recorrer_carpetas_dirs(session, owner, repo, headers, "", carpetas, semaforo)
        resultado = sorted(carpetas)
        cache_carpetas[clave_cache] = (ahora, list(resultado))
        return resultado

    async def _recorrer_carpetas_dirs(
        self, session: aiohttp.ClientSession, owner: str, repo: str, headers: dict, 
        path: str, acumulador: list, semaforo: asyncio.Semaphore
    ) -> None:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        async with semaforo:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return
                elementos = await resp.json()

        for elem in elementos:
            if elem["type"] == "dir":
                acumulador.append(elem["path"])
                await self._recorrer_carpetas_dirs(session, owner, repo, headers, elem["path"], acumulador, semaforo)

    async def obtener_info_y_contenido(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> Optional[Dict[str, Any]]:
        headers = self._headers(token)
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        async with semaforo:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                datos = await resp.json()
        return {"sha": datos["sha"], "content": datos.get("content", "")}

    async def subir_archivo(
        self, owner: str, repo: str, token: str, path: str, contenido: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        headers = self._headers(token)
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        payload = {
            "message": mensaje_commit,
            "content": base64.b64encode(contenido.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 201):
                    error_body = await resp.text()
                    raise RuntimeError(f"GitHub devolvió {resp.status}: {error_body}")
        if invalidar_cache_fn:
            invalidar_cache_fn()

    async def subir_o_actualizar_archivo(
        self, owner: str, repo: str, token: str, path: str, contenido: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> bool:
        headers = self._headers(token)
        async with aiohttp.ClientSession() as session:
            info = await self.obtener_info_y_contenido(session, owner, repo, token, path, semaforo)

        payload = {
            "message": mensaje_commit,
            "content": base64.b64encode(contenido.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        es_actualizacion = info is not None
        if es_actualizacion:
            payload["sha"] = info["sha"]

        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 201):
                    error_body = await resp.text()
                    raise RuntimeError(f"GitHub devolvió {resp.status}: {error_body}")
        if invalidar_cache_fn:
            invalidar_cache_fn()
        return es_actualizacion

    async def append_log_okf(
        self, owner: str, repo: str, token: str, branch: str, entrada: str, 
        mensaje_commit: str, semaforo: asyncio.Semaphore
    ) -> None:
        headers = self._headers(token)
        async with aiohttp.ClientSession() as session:
            info = await self.obtener_info_y_contenido(session, owner, repo, token, OKF_LOG_PATH, semaforo)
        if info is None:
            raise RuntimeError(f"No se ha encontrado «{OKF_LOG_PATH}» en el repo; no se puede hacer append.")

        contenido_actual = base64.b64decode(info["content"]).decode("utf-8")
        contenido_nuevo = contenido_actual.rstrip("\n") + "\n\n" + entrada.strip() + "\n"

        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{OKF_LOG_PATH}"
        payload = {
            "message": mensaje_commit,
            "content": base64.b64encode(contenido_nuevo.encode("utf-8")).decode("ascii"),
            "sha": info["sha"],
            "branch": branch,
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 201):
                    error_body = await resp.text()
                    raise RuntimeError(f"GitHub devolvió {resp.status} al añadir a {OKF_LOG_PATH}: {error_body}")

    async def borrar_archivo(
        self, owner: str, repo: str, token: str, path: str, branch: str, 
        mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        headers = self._headers(token)
        async with aiohttp.ClientSession() as session:
            info = await self.obtener_info_y_contenido(session, owner, repo, token, path, semaforo)
        if info is None:
            raise RuntimeError(f"No se ha encontrado el archivo «{path}» para eliminarlo.")

        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        payload = {"message": mensaje_commit, "sha": info["sha"], "branch": branch}
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 204):
                    error_body = await resp.text()
                    raise RuntimeError(f"GitHub devolvió {resp.status} al borrar {path}: {error_body}")
        if invalidar_cache_fn:
            invalidar_cache_fn()

    async def mover_archivo(
        self, owner: str, repo: str, token: str, old_path: str, new_path: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        headers = self._headers(token)
        async with aiohttp.ClientSession() as session:
            info = await self.obtener_info_y_contenido(session, owner, repo, token, old_path, semaforo)
        if info is None:
            raise RuntimeError(f"El archivo «{old_path}» no existe; no se puede mover.")

        url_destino = f"https://api.github.com/repos/{owner}/{repo}/contents/{new_path}"
        payload_crear = {
            "message": mensaje_commit,
            "content": info["content"],
            "branch": branch,
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(url_destino, headers=headers, json=payload_crear) as resp:
                if resp.status not in (200, 201):
                    error_body = await resp.text()
                    raise RuntimeError(f"GitHub devolvió {resp.status} al crear destino en {new_path}: {error_body}")

        await self.borrar_archivo(owner, repo, token, old_path, branch, f"Borrar por movimiento a {new_path}", semaforo, invalidar_cache_fn)

    async def obtener_historial_fichero(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> List[Dict[str, Any]]:
        headers = self._headers(token)
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"path": path, "per_page": 20}
        async with semaforo:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    return []
                lista = await resp.json()
        resultado = []
        for c in lista:
            resultado.append({
                "hash": c.get("sha", "")[:8],
                "mensaje": c.get("commit", {}).get("message", "").split("\n")[0],
                "autor": c.get("commit", {}).get("author", {}).get("name", "Desconocido"),
                "fecha": c.get("commit", {}).get("author", {}).get("date", ""),
            })
        return resultado

    async def recorrer_carpeta_con_sha(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> List[Dict[str, Any]]:
        headers = self._headers(token)
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        ficheros = []
        async with semaforo:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return ficheros
                elementos = await resp.json()

        for elem in elementos:
            if elem["type"] == "dir":
                subs = await self.recorrer_carpeta_con_sha(session, owner, repo, token, elem["path"], semaforo)
                ficheros.extend(subs)
            elif elem["type"] == "file":
                ficheros.append({"path": elem["path"], "sha": elem["sha"]})
        return ficheros


class GitLabClient(GitProvider):
    """Implementación del proveedor Git para la API REST v4 de GitLab (gitlab.com o self-hosted)."""

    def __init__(self, base_url: str = "https://gitlab.com"):
        self.base_url = base_url.rstrip("/")

    def _headers(self, token: str) -> dict:
        headers = {"User-Agent": "Moodle-GitMetrics-Maubot/1.0"}
        if token:
            headers["PRIVATE-TOKEN"] = token
        return headers

    def _pid(self, owner: str, repo: str) -> str:
        return urllib.parse.quote(f"{owner}/{repo}", safe="")

    async def obtener_documentacion(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        filtro: str, cache_docs: dict, ttl_segundos: int, semaforo: asyncio.Semaphore, log: Any
    ) -> str:
        ahora = time.time()
        clave_cache = (owner, repo, filtro.lower())
        if clave_cache in cache_docs:
            ts_guardado, contenido_cached = cache_docs[clave_cache]
            if ahora - ts_guardado < ttl_segundos:
                if log:
                    log.info(f"[github_bot] Usando caché en memoria para documentación (filtro: '{filtro}')")
                return contenido_cached

        headers = self._headers(token)
        textos = await self._recorrer_carpeta_docs(session, owner, repo, headers, "", filtro, semaforo, log)
        contenido_total = "\n\n".join(textos)
        cache_docs[clave_cache] = (ahora, contenido_total)
        return contenido_total

    async def _recorrer_carpeta_docs(
        self, session: aiohttp.ClientSession, owner: str, repo: str, headers: dict, 
        path: str, filtro: str, semaforo: asyncio.Semaphore, log: Any
    ) -> List[str]:
        pid = self._pid(owner, repo)
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/tree"
        params = {"recursive": "true", "per_page": 100}
        if path:
            params["path"] = path

        elementos = []
        page = 1
        async with semaforo:
            if log:
                log.info(f"[github_bot] Consultando GitLab árbol: {url}")
            while True:
                params["page"] = page
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        break
                    l = await resp.json()
                    if not isinstance(l, list) or not l:
                        break
                    elementos.extend(l)
                    if len(l) < 100:
                        break
                    page += 1

        file_tasks = []
        for elem in elementos:
            if elem.get("type") == "blob" and elem.get("path", "").endswith((".md", ".txt")):
                nombre = elem["path"].split("/")[-1]
                if nombre.lower() in FICHEROS_EXCLUIDOS_CONTEXTO:
                    continue
                if filtro and filtro.lower() not in elem["path"].lower():
                    continue
                file_tasks.append(self._descargar_fichero(session, owner, repo, elem["path"], headers, semaforo, log))

        textos = []
        if file_tasks:
            resultados = await asyncio.gather(*file_tasks, return_exceptions=True)
            for res in resultados:
                if isinstance(res, str) and res.strip():
                    textos.append(res)
        return textos

    async def _descargar_fichero(
        self, session: aiohttp.ClientSession, owner: str, repo: str, path: str, 
        headers: dict, semaforo: asyncio.Semaphore, log: Any
    ) -> str:
        pid = self._pid(owner, repo)
        enc_path = urllib.parse.quote(path, safe="")
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/files/{enc_path}/raw"
        async with semaforo:
            if log:
                log.info(f"[github_bot] Descargando archivo GitLab: {path}")
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    contenido = await resp.text()
                    return f"## Archivo: {path}\n{contenido}"
        return ""

    async def listar_rutas(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, cache_rutas: dict, ttl_segundos: int, semaforo: asyncio.Semaphore
    ) -> List[str]:
        ahora = time.time()
        clave_cache = (owner, repo, path)
        if clave_cache in cache_rutas:
            ts_guardado, rutas_cached = cache_rutas[clave_cache]
            if ahora - ts_guardado < ttl_segundos:
                return list(rutas_cached)

        headers = self._headers(token)
        pid = self._pid(owner, repo)
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/tree"
        params = {"recursive": "true", "per_page": 100}
        if path:
            params["path"] = path

        rutas = []
        page = 1
        async with semaforo:
            while True:
                params["page"] = page
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        break
                    l = await resp.json()
                    if not isinstance(l, list) or not l:
                        break
                    for elem in l:
                        if elem.get("type") == "blob" and elem.get("path", "").endswith((".md", ".txt")):
                            rutas.append(elem["path"])
                    if len(l) < 100:
                        break
                    page += 1

        cache_rutas[clave_cache] = (ahora, list(rutas))
        return rutas

    async def listar_carpetas(
        self, owner: str, repo: str, token: str, cache_carpetas: dict, 
        ttl_segundos: int, semaforo: asyncio.Semaphore
    ) -> List[str]:
        ahora = time.time()
        clave_cache = (owner, repo)
        if clave_cache in cache_carpetas:
            ts_guardado, carpetas_cached = cache_carpetas[clave_cache]
            if ahora - ts_guardado < ttl_segundos:
                return list(carpetas_cached)

        headers = self._headers(token)
        pid = self._pid(owner, repo)
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/tree"
        params = {"recursive": "true", "per_page": 100}

        carpetas = set()
        page = 1
        async with aiohttp.ClientSession() as session:
            async with semaforo:
                while True:
                    params["page"] = page
                    async with session.get(url, headers=headers, params=params) as resp:
                        if resp.status != 200:
                            break
                        l = await resp.json()
                        if not isinstance(l, list) or not l:
                            break
                        for elem in l:
                            if elem.get("type") == "tree":
                                carpetas.add(elem["path"])
                            else:
                                parts = elem.get("path", "").split("/")
                                if len(parts) > 1:
                                    carpetas.add("/".join(parts[:-1]))
                        if len(l) < 100:
                            break
                        page += 1

        resultado = sorted(list(carpetas))
        cache_carpetas[clave_cache] = (ahora, list(resultado))
        return resultado

    async def obtener_info_y_contenido(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> Optional[Dict[str, Any]]:
        headers = self._headers(token)
        pid = self._pid(owner, repo)
        enc_path = urllib.parse.quote(path, safe="")
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/files/{enc_path}"
        params = {"ref": "main"}
        async with semaforo:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    return None
                datos = await resp.json()
        return {
            "sha": datos.get("content_sha256", datos.get("last_commit_id", "")),
            "content": datos.get("content", ""),
        }

    async def subir_archivo(
        self, owner: str, repo: str, token: str, path: str, contenido: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        await self.subir_o_actualizar_archivo(owner, repo, token, path, contenido, branch, mensaje_commit, semaforo, invalidar_cache_fn)

    async def subir_o_actualizar_archivo(
        self, owner: str, repo: str, token: str, path: str, contenido: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> bool:
        headers = self._headers(token)
        pid = self._pid(owner, repo)
        enc_path = urllib.parse.quote(path, safe="")
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/files/{enc_path}"

        async with aiohttp.ClientSession() as session:
            info = await self.obtener_info_y_contenido(session, owner, repo, token, path, semaforo)

        payload = {
            "branch": branch,
            "commit_message": mensaje_commit,
            "content": contenido,
            "encoding": "text",
        }
        es_actualizacion = info is not None
        metodo = "put" if es_actualizacion else "post"

        async with aiohttp.ClientSession() as session:
            func = getattr(session, metodo)
            async with func(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 201):
                    error_body = await resp.text()
                    raise RuntimeError(f"GitLab devolvió {resp.status}: {error_body}")
        if invalidar_cache_fn:
            invalidar_cache_fn()
        return es_actualizacion

    async def append_log_okf(
        self, owner: str, repo: str, token: str, branch: str, entrada: str, 
        mensaje_commit: str, semaforo: asyncio.Semaphore
    ) -> None:
        async with aiohttp.ClientSession() as session:
            info = await self.obtener_info_y_contenido(session, owner, repo, token, OKF_LOG_PATH, semaforo)
        if info is None:
            raise RuntimeError(f"No se ha encontrado «{OKF_LOG_PATH}» en el repo; no se puede hacer append.")

        contenido_actual = base64.b64decode(info["content"]).decode("utf-8") if info.get("content") else ""
        contenido_nuevo = contenido_actual.rstrip("\n") + "\n\n" + entrada.strip() + "\n"
        await self.subir_o_actualizar_archivo(owner, repo, token, OKF_LOG_PATH, contenido_nuevo, branch, mensaje_commit, semaforo, None)

    async def borrar_archivo(
        self, owner: str, repo: str, token: str, path: str, branch: str, 
        mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        headers = self._headers(token)
        pid = self._pid(owner, repo)
        enc_path = urllib.parse.quote(path, safe="")
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/files/{enc_path}"
        payload = {"branch": branch, "commit_message": mensaje_commit}

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 204):
                    error_body = await resp.text()
                    raise RuntimeError(f"GitLab devolvió {resp.status} al borrar {path}: {error_body}")
        if invalidar_cache_fn:
            invalidar_cache_fn()

    async def mover_archivo(
        self, owner: str, repo: str, token: str, old_path: str, new_path: str, 
        branch: str, mensaje_commit: str, semaforo: asyncio.Semaphore, invalidar_cache_fn: Any
    ) -> None:
        headers = self._headers(token)
        pid = self._pid(owner, repo)
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/commits"
        payload = {
            "branch": branch,
            "commit_message": mensaje_commit,
            "actions": [
                {
                    "action": "move",
                    "previous_path": old_path,
                    "file_path": new_path,
                }
            ],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 201):
                    error_body = await resp.text()
                    raise RuntimeError(f"GitLab devolvió {resp.status} al mover {old_path} a {new_path}: {error_body}")
        if invalidar_cache_fn:
            invalidar_cache_fn()

    async def obtener_historial_fichero(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> List[Dict[str, Any]]:
        headers = self._headers(token)
        pid = self._pid(owner, repo)
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/commits"
        params = {"path": path, "per_page": 20}
        async with semaforo:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    return []
                lista = await resp.json()
        resultado = []
        for c in lista:
            resultado.append({
                "hash": c.get("id", "")[:8],
                "mensaje": c.get("title", "").split("\n")[0],
                "autor": c.get("author_name", "Desconocido"),
                "fecha": c.get("authored_date", ""),
            })
        return resultado

    async def recorrer_carpeta_con_sha(
        self, session: aiohttp.ClientSession, owner: str, repo: str, token: str, 
        path: str, semaforo: asyncio.Semaphore
    ) -> List[Dict[str, Any]]:
        headers = self._headers(token)
        pid = self._pid(owner, repo)
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/tree"
        params = {"recursive": "true", "per_page": 100}
        if path:
            params["path"] = path

        ficheros = []
        page = 1
        async with semaforo:
            while True:
                params["page"] = page
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        break
                    l = await resp.json()
                    if not isinstance(l, list) or not l:
                        break
                    for elem in l:
                        if elem.get("type") == "blob":
                            ficheros.append({"path": elem["path"], "sha": elem.get("id", "")})
                    if len(l) < 100:
                        break
                    page += 1
        return ficheros


def get_git_client(config: dict) -> GitProvider:
    provider = str(config.get("provider", "")).strip().lower()
    repo_url = str(config.get("repo_url", "")).strip().lower()

    if provider == "gitlab" or "gitlab" in repo_url:
        gitlab_url = str(config.get("gitlab_url", "https://gitlab.com")).strip()
        return GitLabClient(base_url=gitlab_url)
    elif provider == "github" or "github.com" in repo_url:
        return GitHubClient()
    else:
        # Por defecto gitlab según preferencia del usuario
        gitlab_url = str(config.get("gitlab_url", "https://gitlab.com")).strip()
        return GitLabClient(base_url=gitlab_url)
