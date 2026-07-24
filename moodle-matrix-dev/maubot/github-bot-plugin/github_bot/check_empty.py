import asyncio, aiohttp, os
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

    import logging
    async with aiohttp.ClientSession() as s:
        rutas = await git._recorrer_carpeta_docs(s, owner, repo, {"PRIVATE-TOKEN": token}, "", ".md", sem, logging.getLogger("dummy"))
        print("Total md files across repo:", len(rutas))
        for path in sorted(rutas):
            info = await git.obtener_info_y_contenido(s, owner, repo, token, path, sem)
            if not info or not info.get("content"):
                print(f"ZERO BYTES OR EMPTY INFO: {path}")
            else:
                import base64
                txt = base64.b64decode(info["content"]).decode("utf-8", errors="ignore").strip()
                if len(txt) == 0:
                    print(f"ZERO BYTE CONTENT: {path}")
                else:
                    body = txt.split("---")[-1].strip() if "---" in txt else txt
                    if len(body) < 80:
                        print(f"STUB / SHORT NOTE (< 80 chars body): {path} -> Body: {body[:60]!r}")

if __name__ == "__main__":
    asyncio.run(main())
