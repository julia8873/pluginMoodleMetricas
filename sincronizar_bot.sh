#!/usr/bin/env bash
# ==============================================================================
# sincronizar_bot.sh - Aplica cambios de base-config.yaml al bot en ejecución
# ==============================================================================
# Úsalo siempre que modifiques manualmente las claves API de IA o configuraciones
# dentro de moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/base-config.yaml

set -e

echo "======================================================================"
echo " Sincronizando configuración de Maubot..."
echo "======================================================================"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^maubot$'; then
    echo "[i] Inyectando base-config.yaml en la base de datos interna..."
    
    docker exec maubot python3 -c '
import sqlite3
import sys

db_path = "/data/maubot.db"
config_path = "/plugin-src/base-config.yaml"

try:
    # Leer el archivo modificado por el usuario
    with open(config_path, "r", encoding="utf-8") as f:
        new_config = f.read()

    # Sobrescribir la configuración de la instancia activa
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    filas = cur.execute("SELECT id FROM instance").fetchall()
    for (row_id,) in filas:
        cur.execute("UPDATE instance SET config = ? WHERE id = ?", (new_config, row_id))
        
    conn.commit()
    conn.close()
    print("[OK] Sincronización de base de datos exitosa.")
except Exception as e:
    print(f"[!] Error al actualizar la base de datos: {e}")
    sys.exit(1)
'

    echo "[i] Reiniciando el contenedor de Maubot para aplicar..."
    (cd moodle-matrix-dev && docker compose restart maubot >/dev/null 2>&1)
    echo "[OK] ¡Bot actualizado y reiniciado!"
else
    echo "[!] El contenedor maubot no está en ejecución."
    echo "    Levanta el entorno Docker primero."
fi
