#!/usr/bin/env bash
# ==============================================================================
# configurar_git.sh — Conexión unificada automática para Moodle, Maubot y Obsidian
# ==============================================================================

set -e

URL=""
TOKEN=""
BRANCH="main"

# Parsear argumentos
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --url=*) URL="${1#*=}" ;;
        --token=*) TOKEN="${1#*=}" ;;
        --branch=*) BRANCH="${1#*=}" ;;
        -u|--url) URL="$2"; shift ;;
        -t|--token) TOKEN="$2"; shift ;;
        -b|--branch) BRANCH="$2"; shift ;;
        *) echo "Parámetro desconocido: $1"; exit 1 ;;
    esac
    shift
done

# Solicitar interactivamente si no se pasaron por parámetro
if [ -z "$URL" ]; then
    echo "======================================================================"
    echo " Configuración Unificada de Repositorio Git (GitLab / GitHub)"
    echo "======================================================================"
    read -p "URL del repositorio (ej. https://gitlab.com/<tu_usuario>/<tu_repo>): " URL
fi

if [ -z "$TOKEN" ]; then
    read -p "Token de acceso (glpat-... o ghp-...): " TOKEN
fi

URL=$(echo "$URL" | sed 's/\/$//')

if [ -z "$URL" ]; then
    echo "Error: La URL del repositorio no puede estar vacía."
    exit 1
fi

# Detectar proveedor y extraer componentes
PROVIDER="github"
GITLAB_URL="https://gitlab.com"
OWNER=""
REPO=""

if [[ "$URL" =~ ^https?://([^/]+)/([^/]+)/([^/.]+)(\.git)?$ ]]; then
    DOMAIN="${BASH_REMATCH[1]}"
    OWNER="${BASH_REMATCH[2]}"
    REPO="${BASH_REMATCH[3]}"
    
    if [[ "$DOMAIN" == *"gitlab"* ]] || [[ "$DOMAIN" == *"osl.ugr.es"* ]] || [[ "$URL" == *"gitlab"* ]]; then
        PROVIDER="gitlab"
        if [[ "$URL" =~ ^(https?://[^/]+) ]]; then
            GITLAB_URL="${BASH_REMATCH[1]}"
        fi
    else
        PROVIDER="github"
    fi
else
    echo "Error: El formato de URL ($URL) no es válido. Debe ser del tipo https://gitlab.com/usuario/repositorio"
    exit 1
fi

echo ""
echo "======================================================================"
echo " Sincronizando Maubot, Moodle y Obsidian..."
echo " Proveedor: $PROVIDER | Repo: $OWNER/$REPO | Rama: $BRANCH"
echo "======================================================================"

# 1. Configurar Maubot (base-config.yaml)
BOT_CONFIG_FILE="moodle-matrix-dev/github-bot-plugin/github-bot-plugin/base-config.yaml"

if [ -f "$BOT_CONFIG_FILE" ]; then
    python3 -c '
import sys, re

file_path = sys.argv[1]
provider = sys.argv[2]
repo_url = sys.argv[3]
gitlab_url = sys.argv[4]
token = sys.argv[5]
owner = sys.argv[6]
repo = sys.argv[7]
branch = sys.argv[8]

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(r"^provider:.*$", f"provider: \"{provider}\"", content, flags=re.M)
content = re.sub(r"^repo_url:.*$", f"repo_url: \"{repo_url}\"", content, flags=re.M)
content = re.sub(r"^gitlab_url:.*$", f"gitlab_url: \"{gitlab_url}\"", content, flags=re.M)
content = re.sub(r"^default_owner:.*$", f"default_owner: \"{owner}\"", content, flags=re.M)
content = re.sub(r"^default_repo:.*$", f"default_repo: \"{repo}\"", content, flags=re.M)
content = re.sub(r"^default_branch:.*$", f"default_branch: \"{branch}\"", content, flags=re.M)

if provider == "gitlab":
    if token:
        content = re.sub(r"^gitlab_token:.*$", f"gitlab_token: \"{token}\"", content, flags=re.M)
    content = re.sub(r"^github_token:.*$", "github_token: \"\"", content, flags=re.M)
else:
    if token:
        content = re.sub(r"^github_token:.*$", f"github_token: \"{token}\"", content, flags=re.M)
    content = re.sub(r"^gitlab_token:.*$", "gitlab_token: \"\"", content, flags=re.M)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
' "$BOT_CONFIG_FILE" "$PROVIDER" "$URL" "$GITLAB_URL" "$TOKEN" "$OWNER" "$REPO" "$BRANCH"

    echo "[OK] Configuración del bot Maubot ($BOT_CONFIG_FILE) actualizada."
    
    # Si Maubot está ejecutándose en Docker, actualizar base de datos interna y reiniciar
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^maubot$'; then
        echo "[i] Actualizando base de datos interna de Maubot..."
        docker exec maubot python3 -c '
import sqlite3, re, sys
db_path = "/data/maubot.db"
provider = sys.argv[1]
repo_url = sys.argv[2]
gitlab_url = sys.argv[3]
token = sys.argv[4]
owner = sys.argv[5]
repo = sys.argv[6]
branch = sys.argv[7]

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for row_id, config in cur.execute("SELECT id, config FROM instance").fetchall():
        if not config: continue
        config = re.sub(r"^provider:.*$", f"provider: \"{provider}\"", config, flags=re.M)
        config = re.sub(r"^repo_url:.*$", f"repo_url: \"{repo_url}\"", config, flags=re.M)
        config = re.sub(r"^gitlab_url:.*$", f"gitlab_url: \"{gitlab_url}\"", config, flags=re.M)
        config = re.sub(r"^default_owner:.*$", f"default_owner: \"{owner}\"", config, flags=re.M)
        config = re.sub(r"^default_repo:.*$", f"default_repo: \"{repo}\"", config, flags=re.M)
        config = re.sub(r"^default_branch:.*$", f"default_branch: \"{branch}\"", config, flags=re.M)
        if provider == "gitlab":
            if token:
                config = re.sub(r"^gitlab_token:.*$", f"gitlab_token: \"{token}\"", config, flags=re.M)
            config = re.sub(r"^github_token:.*$", "github_token: \"\"", config, flags=re.M)
        else:
            if token:
                config = re.sub(r"^github_token:.*$", f"github_token: \"{token}\"", config, flags=re.M)
            config = re.sub(r"^gitlab_token:.*$", "gitlab_token: \"\"", config, flags=re.M)
        cur.execute("UPDATE instance SET config = ? WHERE id = ?", (config, row_id))
    conn.commit()
    conn.close()
except Exception as e:
    pass
' "$PROVIDER" "$URL" "$GITLAB_URL" "$TOKEN" "$OWNER" "$REPO" "$BRANCH" || true

        echo "[i] Reiniciando contenedor de Maubot para aplicar los cambios..."
        (cd moodle-matrix-dev && docker compose restart maubot >/dev/null 2>&1)
        echo "[OK] Maubot reiniciado y conectado al repositorio."
    fi
else
    echo "[!] No se encontró el archivo $BOT_CONFIG_FILE. Omitiendo Maubot."
fi

# 2. Configurar Moodle y Obsidian vía CLI dentro del contenedor Docker
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^moodle-app$'; then
    echo "[i] Sincronizando Moodle y Obsidian dentro del contenedor..."
    
    # Asegurar que el plugin y los scripts estén en el contenedor
    docker cp gitmetrics/. moodle-app:/bitnami/moodle/blocks/gitmetrics/ >/dev/null 2>&1 || true
    docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics >/dev/null 2>&1 || true
    
    # Ejecutar setup_git.php en Moodle
    docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_git.php --url="$URL" --token="$TOKEN" --branch="$BRANCH"
else
    echo "[!] El contenedor moodle-app no está en ejecución. Para aplicar cambios en Moodle, levanta Docker y ejecuta:"
    echo "    docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_git.php --url=\"$URL\" --token=\"$TOKEN\""
fi

echo ""
echo "======================================================================"
echo " ¡Listo! Moodle, Maubot y Obsidian conectados correctamente a $URL."
echo "======================================================================"
