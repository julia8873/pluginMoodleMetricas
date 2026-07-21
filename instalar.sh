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
docker cp "$PLUGIN_DIR/." moodle-app:/bitnami/moodle/blocks/gitmetrics/

# 4. Ajustar permisos del plugin y carpeta de datos
echo ""
echo "[4/5] Ajustando permisos en el contenedor..."
docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics /bitnami/moodledata
docker exec --user root moodle-app chmod -R 755 /bitnami/moodle/blocks/gitmetrics

# 5. Ejecutar la actualización de la base de datos de Moodle
echo ""
echo "[5/6] Instalando/Actualizando el plugin en la base de datos de Moodle..."
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/upgrade.php --non-interactive

# 6. Crear asignatura dedicada y configurar pestaña de curso
echo ""
echo "[6/7] Creando asignatura dedicada 'Panel de Métricas y BdC' en Moodle..."
docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_course.php

# 7. Configurar automáticamente Matrix, desbloquear red interna y crear sala
echo ""
echo "[7/7] Configurando integración con Matrix y creando sala de chat..."
docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_matrix.php

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
echo "------------------------------------------------------------------------------"
