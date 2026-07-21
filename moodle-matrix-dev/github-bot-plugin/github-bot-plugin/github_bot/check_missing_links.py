import asyncio, aiohttp, os, re, base64, logging
from github_bot.git_client import get_git_client
from ruamel.yaml import YAML

async def main():
    config = {}
    db_path = "/data/maubot.db"
    if os.path.exists(db_path):
        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT config FROM instance WHERE id='dev.julia.githubbot'").fetchone()
        if row and row[0]:
            yaml = YAML()
            config = yaml.load(row[0])
        conn.close()

    git = get_git_client(config)
    sem = asyncio.Semaphore(5)
    owner = config["default_owner"]
    repo = config["default_repo"]
    token = config["gitlab_token"]
    branch = config.get("default_branch", "main")

    async with aiohttp.ClientSession() as s:
        rutas = await git._recorrer_carpeta_docs(s, owner, repo, {"PRIVATE-TOKEN": token}, "", ".md", sem, logging.getLogger("dummy"))
        nombres_existentes = set()
        for r in rutas:
            base = r.split("/")[-1].replace(".md", "").lower()
            nombres_existentes.add(base)
            nombres_existentes.add(r.lower())
            nombres_existentes.add(r.replace(".md", "").lower())

        enlaces_encontrados = {}
        for r in sorted(rutas):
            if not r.startswith("okf/"):
                continue
            info = await git.obtener_info_y_contenido(s, owner, repo, token, r, sem)
            if not info or not info.get("content"):
                continue
            txt = base64.b64decode(info["content"]).decode("utf-8", errors="ignore")
            # buscar [[...]]
            links = re.findall(r"\[\[([^\]]+)\]\]", txt)
            for l in links:
                objetivo = l.split("|")[0].strip()
                base_obj = objetivo.split("/")[-1].replace(".md", "").lower().strip()
                if base_obj not in nombres_existentes and objetivo.lower() not in nombres_existentes:
                    enlaces_encontrados.setdefault(base_obj, []).append(r)

        print("\n=== ENLACES SIN FICHERO CORRESPONDIENTE EN GITLAB (MISSING LINKS) ===")
        for obj, fuentes in sorted(enlaces_encontrados.items()):
            print(f"MISSING: '{obj}' -> mencionado en: {', '.join(set(fuentes))}")

if __name__ == "__main__":
    asyncio.run(main())
