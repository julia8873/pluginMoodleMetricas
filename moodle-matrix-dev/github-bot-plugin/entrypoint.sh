#!/bin/sh
# --8<-- [start:file_desc]
# entrypoint.sh – Compila el plugin de maubot desde el código fuente
# y arranca el servidor maubot.
#
# El .mbp (maubot plugin bundle) es simplemente un ZIP con el código fuente
# del plugin. Se construye en cada inicio del contenedor para asegurar que
# siempre se usa la versión más reciente del código.

set -e

PLUGIN_SRC="/plugin-src"
PLUGIN_OUT="/data/plugins"
PLUGIN_ID="dev.julia.githubbot"

# Extraer la versión del maubot.yaml del plugin
VERSION=$(grep '^version:' "$PLUGIN_SRC/maubot.yaml" | awk '{print $2}')
MBP_FILE="$PLUGIN_OUT/${PLUGIN_ID}-v${VERSION}.mbp"

echo "[entrypoint] Compilando plugin ${PLUGIN_ID} v${VERSION}..."
mkdir -p "$PLUGIN_OUT"

# Eliminar .mbp antiguos de este plugin para evitar duplicados
rm -f "$PLUGIN_OUT/${PLUGIN_ID}"*.mbp

# Construir el .mbp en un directorio temporal
TMP_BUILD=$(mktemp -d)

cd "$PLUGIN_SRC"

# Copiar los ficheros del plugin (excluyendo bytecode Python)
cp maubot.yaml base-config.yaml "$TMP_BUILD/"

find github_bot -type f \
    ! -name "*.pyc" \
    ! -name "*.pyo" \
    ! -path "*/__pycache__/*" \
    | while IFS= read -r f; do
        mkdir -p "$TMP_BUILD/$(dirname "$f")"
        cp "$f" "$TMP_BUILD/$f"
    done

# Crear el fichero .mbp (ZIP)
cd "$TMP_BUILD"
zip -r "$MBP_FILE" .
cd /
rm -rf "$TMP_BUILD"

echo "[entrypoint] Plugin construido: $MBP_FILE"

# Arrancar el servidor maubot
exec python -m maubot -c /data/config.yaml "$@"
# --8<-- [end:file_desc]
