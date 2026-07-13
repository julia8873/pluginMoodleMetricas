#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Script de instalación y arranque automático de block_gitmetrics en Moodle
# ------------------------------------------------------------------------------

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/moodle-matrix-dev"
PLUGIN_DIR="$SCRIPT_DIR/gitmetrics"

echo "------------------------------------------------------------------------------"
echo " INICIANDO ENTORNO MOODLE & MATRIX + PLUGIN GITMETRICS"
echo "------------------------------------------------------------------------------"

# 1. Levantar contenedores Docker
echo ""
echo "[1/5] Levantando contenedores Docker..."
cd "$DOCKER_DIR"
docker compose up -d

# 2. Esperar a que Moodle esté inicializado y escuchando
echo ""
echo "[2/5] Esperando a que Moodle esté completamente iniciado..."
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
echo "[3/5] Copiando el plugin 'gitmetrics' en Moodle..."
docker cp "$PLUGIN_DIR" moodle-app:/bitnami/moodle/blocks/gitmetrics

# 4. Ajustar permisos del plugin
echo ""
echo "[4/5] Ajustando permisos del directorio en el contenedor..."
docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics
docker exec --user root moodle-app chmod -R 755 /bitnami/moodle/blocks/gitmetrics

# 5. Ejecutar la actualización de la base de datos de Moodle
echo ""
echo "[5/5] Instalando/Actualizando el plugin en la base de datos de Moodle..."
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/upgrade.php --non-interactive

echo ""
echo "------------------------------------------------------------------------------"
echo " ¡TODO LISTO! EL ENTORNO Y EL PLUGIN ESTÁN OPERATIVOS"
echo "------------------------------------------------------------------------------"
echo ""
echo " Moodle URL  : http://localhost:8000"
echo " Usuario     : admin"
echo " Contraseña  : adminpass123"
echo ""
echo " Pasos para probar el bloque en Moodle:"
echo "    1. Abre http://localhost:8000 e inicia sesión."
echo "    2. Entra a un curso -> haz clic en 'Activar edición' (Turn editing on)."
echo "    3. Haz clic en 'Añadir un bloque' (Add a block) -> selecciona:"
echo "       - En inglés (idioma por defecto de Moodle): 'Git Knowledge Base Metrics'"
echo "       - En español: 'Métricas de Base de Conocimiento Git'"
echo "    4. Configura el bloque con el repo: https://github.com/julia8873/bdc-prueba"
echo "------------------------------------------------------------------------------"
