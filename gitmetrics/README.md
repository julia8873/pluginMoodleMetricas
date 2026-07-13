# block_gitmetrics

Plugin de bloque para Moodle que analiza un repositorio GitHub con estructura OKF y muestra métricas cuantitativas de la Base de Conocimiento.

---

## Estructura del plugin

```
gitmetrics/
├── block_gitmetrics.php          Clase principal del bloque
├── version.php                   Versión y compatibilidad
├── settings.php                  Configuración global (admin): token, TTL caché, rama
├── edit_form.php                 Configuración por instancia: URL repo, rama, refresco
├── renderer.php                  Renderizador HTML con CSS inline
├── classes/
│   ├── github_client.php         Cliente HTTP para GitHub API y raw.githubusercontent.com
│   ├── markdown_parser.php       Parser de frontmatter YAML, enlaces y validación Markdown
│   ├── metrics_calculator.php    Cálculo de las 4 categorías de métricas
│   └── metrics_cache.php         Caché de resultados en BD Moodle con TTL
├── db/
│   ├── access.php                Permisos/capabilities
│   ├── install.xml               Esquema de base de datos (tabla de caché)
│   ├── upgrade.php               Migraciones de versión
│   └── events.php                Suscripción a eventos (vacío)
└── lang/
    ├── en/block_gitmetrics.php   Cadenas en inglés
    └── es/block_gitmetrics.php   Cadenas en español
```

---

## Requisitos

- Moodle 4.2 o superior (`requires = 2022041900`)
- Entorno Docker con `moodle-matrix-dev` levantado
- WSL con Docker instalado

---

## Instalación paso a paso

> Todos los comandos se ejecutan desde WSL.
> Directorio de trabajo: `/mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev`
> Moodle disponible en: `http://localhost:8000` — usuario: `admin` / contraseña: `adminpass123`

### PASO 1 — Arrancar el entorno Docker

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev

docker compose up -d

# Seguir el arranque (tarda 2-3 min la primera vez)
docker compose logs -f moodle
# Espera hasta ver: "** Moodle setup finished! **" → Ctrl+C
```

### PASO 2 — Copiar el plugin dentro del contenedor

```bash
docker cp \
  /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/gitmetrics \
  moodle-app:/bitnami/moodle/blocks/gitmetrics

# Verificar
docker exec moodle-app ls /bitnami/moodle/blocks/gitmetrics
```

### PASO 3 — Ajustar permisos

```bash
docker exec --user root moodle-app \
  chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics

docker exec --user root moodle-app \
  chmod -R 755 /bitnami/moodle/blocks/gitmetrics
```

### PASO 4 — Instalar el plugin en Moodle

**Por navegador (recomendado):**

Abre `http://localhost:8000/admin/index.php`, inicia sesión como `admin` y haz clic en **"Actualizar base de datos de Moodle ahora"**.

**Por CLI:**

```bash
docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/upgrade.php --non-interactive
```

### PASO 5 — Verificar la tabla en la base de datos

```bash
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "SHOW TABLES LIKE '%gitmetrics%';"
```

Resultado esperado: `mdl_block_gitmetrics_cache`

### PASO 6 — Verificar en el panel de administración

Abre `http://localhost:8000/admin/blocks.php` y comprueba que **"Métricas de Base de Conocimiento Git"** aparece como Activado.

### PASO 7 — Añadir el bloque a un curso

1. Abre un curso en `http://localhost:8000`
2. Activa la edición → **"Activar edición"**
3. Clic en **"Añadir un bloque"** → selecciona **"Métricas de Base de Conocimiento Git"**
4. Haz clic en el **engranaje del bloque** → **"Configurar"**
5. Pega la URL del repositorio, p. ej. `https://github.com/julia8873/bdc-prueba`
6. Guarda → el bloque calculará y mostrará las métricas automáticamente

---

## Comandos Extra

### Configurar el token de GitHub API (aumentar rate-limit)

Sin token la API permite 60 peticiones/hora por IP. Con un Personal Access Token sube a 5 000/hora.

```bash
# Por URL:
# http://localhost:8000/admin/settings.php?section=blocksettinggitmetrics

# Por CLI:
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "UPDATE mdl_config_plugins SET value='ghp_TuTokenAqui' \
      WHERE plugin='block_gitmetrics' AND name='github_token';"

docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/purge_caches.php
```

### Configurar el repositorio por instancia

Desde el navegador: engranaje del bloque → **"Configurar bloque Métricas de Base de Conocimiento Git"** → campo **"URL del Repositorio GitHub"**.

> **Nota:** Moodle elimina el prefijo `config_` al serializar los campos del formulario.
> El campo `config_github_url` del formulario se guarda y lee como `$this->config->github_url`.

Ver qué está guardado en la BD:

```bash
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "SELECT id, blockname, configdata FROM mdl_block_instances WHERE blockname='gitmetrics';"
```

### Consultar la caché de métricas

```bash
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "SELECT blockinstanceid, repo_url, FROM_UNIXTIME(timemodified) AS ultima_actualizacion
      FROM mdl_block_gitmetrics_cache;"
```

### Forzar el recálculo de métricas

**Opción 1 — Desde el formulario del bloque:**
Engranaje → Configurar → marcar **"Forzar refresco de caché"** → Guardar.

**Opción 2 — Desde la BD:**
```bash
# Sustituye ID por el id de la instancia del bloque
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "DELETE FROM mdl_block_gitmetrics_cache WHERE blockinstanceid=ID;"
```

### Ver como estudiante

En el curso: avatar (arriba derecha) → **"Cambiar rol a..."** → **"Estudiante"**.
Para volver: mismo menú → **"Volver a mi rol normal"**.

### Limpiar caché

```bash
docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/purge_caches.php
```

### Ver logs de errores

```bash
docker compose logs -f moodle
docker compose logs --tail=50 moodle
```

### Actualizar el plugin tras cambios en el código

```bash
# Copiar solo el archivo modificado (ejemplo: classes/metrics_calculator.php)
docker cp \
  /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/gitmetrics/classes/metrics_calculator.php \
  moodle-app:/bitnami/moodle/blocks/gitmetrics/classes/metrics_calculator.php

docker exec --user root moodle-app \
  chown daemon:daemon /bitnami/moodle/blocks/gitmetrics/classes/metrics_calculator.php

docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/purge_caches.php
```

### Desinstalar el plugin

```bash
docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/uninstall_plugins.php --plugins=block_gitmetrics --run
```

### Parar / reiniciar el entorno

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev

# Parar sin borrar datos
docker compose down

# Reiniciar desde cero (borra todos los datos)
docker compose down -v && docker compose up -d
```
