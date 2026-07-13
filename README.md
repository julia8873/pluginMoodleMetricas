# block_holamundo

Plugin de bloque para Moodle que muestra "Hola Mundo" y un contador de visitas por instancia.

---

## Estructura del plugin

```
holamundo/
├── block_holamundo.php       Clase principal del bloque
├── version.php               Versión y compatibilidad
├── settings.php              Configuración global (admin)
├── edit_form.php             Configuración por instancia
├── classes/
│   └── output/
│       └── renderer.php      Renderizador HTML
├── db/
│   ├── access.php            Permisos/capabilities
│   ├── install.xml           Esquema de base de datos
│   ├── upgrade.php           Migraciones de versión
│   └── events.php            Suscripción a eventos (vacío)
├── lang/
│   ├── en/block_holamundo.php  Cadenas en inglés
│   └── es/block_holamundo.php  Cadenas en español
└── pix/
    └── icon.png              Icono del bloque
```

---

## Requisitos

- Moodle 4.2 o superior (`requires = 2022041900`)
- Entorno Docker con `moodle-matrix-dev` levantado
- WSL con Docker instalado

---

## Instalación paso a paso

> Todos los comandos se ejecutan desde WSL.
> Directorio de trabajo: `/mnt/c/Users/julia/Desktop/PracticasCEPRUD/TutorialPluginMatrix/moodle-matrix-dev`
> Moodle disponible en: `http://localhost:8000` — usuario: `admin` / contraseña: `adminpass123`

### PASO 1 — Arrancar el entorno Docker

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/TutorialPluginMatrix/moodle-matrix-dev

docker compose up -d

# Seguir el arranque (tarda 2-3 min la primera vez)
docker compose logs -f moodle
# Espera hasta ver: "** Moodle setup finished! **" → Ctrl+C
```

### PASO 2 — Copiar el plugin dentro del contenedor

```bash
docker cp \
  /mnt/c/Users/julia/Desktop/PracticasCEPRUD/TutorialPluginMatrix/holamundo \
  moodle-app:/bitnami/moodle/blocks/holamundo

# Verificar
docker exec moodle-app ls /bitnami/moodle/blocks/holamundo
```

### PASO 3 — Ajustar permisos

```bash
docker exec --user root moodle-app \
  chown -R daemon:daemon /bitnami/moodle/blocks/holamundo

docker exec --user root moodle-app \
  chmod -R 755 /bitnami/moodle/blocks/holamundo
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
  -e "SHOW TABLES LIKE '%holamundo%';"
```

Resultado esperado: `mdl_block_holamundo_visitas`

### PASO 6 — Verificar en el panel de administración

Abre `http://localhost:8000/admin/blocks.php` y comprueba que **"Hello World"** aparece como Activado.

### PASO 7 — Añadir el bloque a un curso

1. Abre un curso en `http://localhost:8000`
2. Activa la edición → **"Activar edición"**
3. Clic en **"Añadir un bloque"** → selecciona **"Hello World"**
4. El bloque aparece con **"Hola Mundo"** y el contador de visitas

---

## Comandos Extra

### Configurar el nombre por defecto (global)

```bash
# Por URL:
# http://localhost:8000/admin/settings.php?section=blocksettingholamundo

# Por CLI:
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "UPDATE mdl_config_plugins SET value='Estudiantes' \
      WHERE plugin='block_holamundo' AND name='nombredefecto';"

docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/purge_caches.php
```

### Configurar el nombre por instancia

Desde el navegador: engranaje del bloque → **"Configurar bloque Hello World"** → campo **"Name to greet (per instance)"**.

> **Nota:** Moodle elimina el prefijo `config_` al serializar los campos del formulario.
> El campo `config_nombre` del formulario se guarda y lee como `$this->config->nombre`.

Ver qué está guardado en la BD:

```bash
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "SELECT id, blockname, configdata FROM mdl_block_instances WHERE blockname='holamundo';"
```

### Consultar el contador de visitas

```bash
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "SELECT blockinstanceid, contador, FROM_UNIXTIME(timemodified) AS ultima_visita
      FROM mdl_block_holamundo_visitas;"
```

### Resetear el contador

```bash
# Sustituye ID por el id de la instancia
docker exec moodle-mariadb \
  mysql -u bn_moodle -pmoodle_db_pass bitnami_moodle \
  -e "UPDATE mdl_block_holamundo_visitas SET contador=0 WHERE blockinstanceid=ID;"
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
# Copiar solo el archivo modificado (ejemplo: block_holamundo.php)
docker cp \
  /mnt/c/Users/julia/Desktop/PracticasCEPRUD/TutorialPluginMatrix/holamundo/block_holamundo.php \
  moodle-app:/bitnami/moodle/blocks/holamundo/block_holamundo.php

docker exec --user root moodle-app \
  chown daemon:daemon /bitnami/moodle/blocks/holamundo/block_holamundo.php

docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/purge_caches.php
```

### Desinstalar el plugin

```bash
docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/uninstall_plugins.php --plugins=block_holamundo --run
```

### Parar / reiniciar el entorno

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/TutorialPluginMatrix/moodle-matrix-dev

# Parar sin borrar datos
docker compose down

# Reiniciar desde cero (borra todos los datos)
docker compose down -v && docker compose up -d
```
