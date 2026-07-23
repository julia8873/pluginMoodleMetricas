#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Script de instalación y arranque automático de block_gitmetrics en Moodle
# ------------------------------------------------------------------------------

set -e

GIT_URL=""
GIT_TOKEN=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --url=*) GIT_URL="${1#*=}" ;;
        --token=*) GIT_TOKEN="${1#*=}" ;;
        -u|--url) GIT_URL="$2"; shift ;;
        -t|--token) GIT_TOKEN="$2"; shift ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/moodle-matrix-dev"
PLUGIN_DIR="$SCRIPT_DIR/gitmetrics"

echo "------------------------------------------------------------------------------"
echo " INICIANDO ENTORNO MOODLE & MATRIX + PLUGIN GITMETRICS"
echo "------------------------------------------------------------------------------"

# 0. Crear ficheros de configuración a partir de las plantillas .example
#    (solo si no existen ya, para no sobrescribir credenciales del usuario)
echo ""
echo "[0/8] Comprobando ficheros de configuración..."

copy_if_missing() {
    local example="$1"
    local target="${example%.example}"
    if [ ! -f "$target" ]; then
        cp "$example" "$target"
        echo "      Creado: $target (desde $(basename "$example"))"
    else
        echo "      Ya existe: $target (no se sobrescribe)"
    fi
}

copy_if_missing "$DOCKER_DIR/.env.example"
copy_if_missing "$DOCKER_DIR/synapse-data/homeserver.yaml.example"
copy_if_missing "$DOCKER_DIR/github-bot-plugin/github-bot-plugin/base-config.yaml.example"
copy_if_missing "$DOCKER_DIR/github-bot-plugin/maubot-data/config.yaml.example"

# 1. Levantar contenedores Docker
echo ""
echo "[1/8] Levantando contenedores Docker..."

if ! command -v docker &> /dev/null || ! docker info &> /dev/null; then
    echo ""
    echo "❌ ERROR: No se puede conectar con Docker."
    echo "Por favor, asegúrate de tener abierta la aplicación Docker Desktop."
    echo "Si usas WSL, verifica que la integración de WSL está activada en Docker Desktop (Settings -> Resources -> WSL Integration)."
    exit 1
fi

cd "$DOCKER_DIR"
docker compose up -d

# 2. Esperar a que Moodle esté inicializado y escuchando
echo ""
echo "[2/8] Esperando a que Moodle esté completamente iniciado..."
echo "      (Esto puede tardar unos segundos...)"

MAX_RETRIES=40
COUNTER=0
until docker exec moodle-app php -r "echo 'OK';" &>/dev/null; do
    sleep 3
    COUNTER=$((COUNTER+1))
    if [ $COUNTER -ge $MAX_RETRIES ]; then
        echo "Advertencia: Tiempo de espera superado comprobando PHP en Moodle."
        break
    fi
done

# Esperar adicionalmente a que el servidor web/BD responda en el contenedor
sleep 3
echo "Moodle contenedor activo."

# 3. Copiar el plugin gitmetrics dentro del contenedor
echo ""
echo "[3/8] Copiando el plugin 'gitmetrics' en Moodle..."
docker cp "$PLUGIN_DIR/." moodle-app:/bitnami/moodle/blocks/gitmetrics/

# 4. Ajustar permisos del plugin y carpeta de datos
echo ""
echo "[4/8] Ajustando permisos en el contenedor..."
docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics /bitnami/moodledata /obsidian-vault 2>/dev/null || true
docker exec --user root moodle-app chmod -R 755 /bitnami/moodle/blocks/gitmetrics

# 5. Ejecutar la actualización de la base de datos de Moodle
echo ""
echo "[5/8] Instalando/Actualizando el plugin en la base de datos de Moodle..."
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/upgrade.php --non-interactive

# 6. Crear asignatura dedicada y configurar pestaña de curso
echo ""
echo "[6/8] Creando asignatura dedicada 'Panel de Métricas y BdC' en Moodle..."
docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_course.php

# 7. Configurar automáticamente Matrix, desbloquear red interna y crear sala
echo ""
echo "[7/8] Configurando integración con Matrix y creando sala de chat..."
docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_matrix.php

# 8. Sincronizar e inicializar integración con Obsidian y Git
echo ""
echo "[8/8] Habilitando integración con Obsidian y sincronizando repositorio..."
if [ -n "$GIT_URL" ]; then
    "$SCRIPT_DIR/configurar_git.sh" --url="$GIT_URL" --token="$GIT_TOKEN"
else
    docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_obsidian.php
fi

# Verificación final de permisos para garantizar acceso al servidor web (daemon)
docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics /bitnami/moodledata /obsidian-vault 2>/dev/null || true

echo ""
echo "------------------------------------------------------------------------------"
echo " ¡TODO LISTO! EL ENTORNO Y EL PLUGIN ESTÁN OPERATIVOS"
echo "------------------------------------------------------------------------------"
echo ""
echo " Moodle URL  : http://localhost:8000"
echo " Usuario     : admin"
echo " Contraseña  : adminpass123"
echo ""
echo " Opciones para probar y ver las métricas en Moodle:"
echo "    OPCIÓN 1 - Asignatura Dedicada creada automáticamente:"
echo "       Entrar a http://localhost:8000 -> Entrar al curso 'Panel de Métricas y BdC'."
echo "    OPCIÓN 2 - Pestaña Superior en cualquier asignatura:"
echo "       1. Abre cualquier asignatura (curso)."
echo "       2. En la barra de pestañas superior verás 'Métricas de Base de Conocimiento Git'."
echo "       3. Haz clic para acceder a pantalla completa."
echo ""
echo " Integración con Obsidian (Sincronización Automática):"
echo "    · El vault está sincronizado en el contenedor en: /obsidian-vault"
echo "    · (Mapeado en el host según OBSIDIAN_VAULT_PATH o /tmp/okf-vault-placeholder)"
echo "------------------------------------------------------------------------------"
