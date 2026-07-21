#!/usr/bin/env python3
"""
Script CLI para ejecutar ingesta por lotes en un archivo largo de raw/
directamente desde el terminal.

Uso:
  docker exec --user daemon maubot python3 -m github_bot.ejecutar_ingesta_lotes "raw/00Libro de Teoria Musical - Nestor Crespo-1784644777.md"
"""
import asyncio
import base64
import sys
from ruamel.yaml import YAML
import os
import aiohttp
from datetime import datetime

from .okf_ingest import construir_prompt_ingest_lote, dividir_en_lotes, parsear_respuesta_ingest
from .git_client import get_git_client
from .llm_provider import LLMProvider


async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 -m github_bot.ejecutar_ingesta_lotes <ruta_raw>")
        sys.exit(1)

    ruta_fuente = sys.argv[1]
    if not ruta_fuente.startswith("raw/"):
        ruta_fuente = f"raw/{ruta_fuente}"

    config = {}
    db_path = "/data/maubot.db"
    if os.path.exists(db_path):
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT config FROM instance WHERE id='dev.julia.githubbot'").fetchone()
            if row and row[0]:
                yaml = YAML()
                config = yaml.load(row[0])
            conn.close()
        except Exception as exc:
            print(f"[WARN] No se pudo cargar config de maubot.db: {exc}")

    if not config or not config.get("llm_api_key"):
        config_path = "/plugin-src/base-config.yaml"
        if not os.path.exists(config_path):
            config_path = os.path.join(os.path.dirname(__file__), "..", "base-config.yaml")
        yaml = YAML()
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.load(f)

    provider = config.get("default_provider", "gitlab")
    owner = config.get("default_owner", "julia8873")
    repo = config.get("default_repo", "BdC")
    branch = config.get("default_branch", "main")
    token = config.get("gitlab_token") if provider == "gitlab" else config.get("github_token")

    git = get_git_client(config)
    llm = LLMProvider(config["llm_base_url"], config["llm_api_key"], config["llm_model"])
    semaforo = asyncio.Semaphore(5)

    print(f"=== INGESTA POR LOTES CLI ===")
    print(f"Repositorio: {owner}/{repo} (rama: {branch}) | Fichero: {ruta_fuente}")

    async with aiohttp.ClientSession() as session:
        info = await git.obtener_info_y_contenido(session, owner, repo, token, ruta_fuente, semaforo)
        if not info:
            print(f"[ERROR] No se pudo leer {ruta_fuente} en {owner}/{repo}")
            sys.exit(2)

        contenido_fuente = base64.b64decode(info["content"]).decode("utf-8")
        agents_info = await git.obtener_info_y_contenido(session, owner, repo, token, "AGENTS.md", semaforo)
        if not agents_info:
            print("[ERROR] No se encontró AGENTS.md en el repositorio.")
            sys.exit(3)
        agents_md = base64.b64decode(agents_info["content"]).decode("utf-8")

    lotes = dividir_en_lotes(contenido_fuente, max_lineas=250, solapamiento=30)
    total_lotes = len(lotes)
    nombre_archivo = ruta_fuente.split("/")[-1]
    timestamp_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Dividido en {total_lotes} lotes de ~250 líneas. Procesando con el modelo LLM...")
    creados, actualizados = [], []

    for i, texto_lote in enumerate(lotes, start=1):
        print(f"\n---> [Lote {i}/{total_lotes}] Enviando al LLM...")
        instruccion = construir_prompt_ingest_lote(agents_md, ruta_fuente, nombre_archivo, timestamp_iso, i, total_lotes)
        try:
            respuesta = await llm.generar_texto(instruccion, texto_lote)
            resultado = parsear_respuesta_ingest(respuesta)
        except Exception as exc:
            print(f"[WARN] Error procesando lote {i}: {exc}")
            continue

        for fichero in resultado["ficheros"]:
            path = fichero["path"]
            cont = fichero["contenido"]
            try:
                fue_act = await git.subir_o_actualizar_archivo(
                    owner, repo, token, path, cont, branch,
                    f"INGEST CLI lote {i}/{total_lotes} de '{ruta_fuente}'",
                    semaforo, lambda: None
                )
                (actualizados if fue_act else creados).append(path)
                print(f"   [{'ACT' if fue_act else 'NUEVO'}] {path}")
            except Exception as exc:
                print(f"   [ERROR SUBIENDO {path}]: {exc}")

        if i < total_lotes:
            print("   (Esperando 15s entre lotes para no exceder cuota por minuto del modelo...)")
            await asyncio.sleep(15)

    print(f"\n=== INGESTA POR LOTES FINALIZADA ===")
    print(f"Ficheros nuevos creados: {len(creados)}")
    print(f"Ficheros actualizados: {len(actualizados)}")


if __name__ == "__main__":
    asyncio.run(main())
