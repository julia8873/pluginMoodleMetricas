# pluginMoodleMetricas

Plugin de bloque para Moodle que analiza un repositorio GitHub con estructura OKF y muestra métricas cuantitativas de la Base de Conocimiento.

| Componente | Descripción |
|---|---|
| [`gitmetrics/`](./gitmetrics/README.md) | Plugin de bloque para Moodle: análisis de repositorios GitHub con estructura OKF |
| [`moodle-matrix-dev/`](./moodle-matrix-dev/README.md) | Entorno Docker local con Moodle, MariaDB, Synapse (Matrix), Element Web y Ollama |

---

## Requisitos previos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y corriendo
- WSL (Windows Subsystem for Linux) con Ubuntu
- Git clonado en: `/mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas`

---

## Pasos para poner todo en marcha

### PASO 1 — Levantar el entorno Docker

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev
docker compose up -d
```

### PASO 2 — Esperar a que Moodle arranque

```bash
docker compose logs -f moodle
```

Espera hasta ver esta línea y pulsa **Ctrl+C**:

```
** Moodle setup finished! **
```

> La primera vez puede tardar 2-3 minutos.

### PASO 3 — Copiar el plugin dentro del contenedor

```bash
docker cp \
  /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/gitmetrics \
  moodle-app:/bitnami/moodle/blocks/gitmetrics
```

### PASO 4 — Ajustar permisos

```bash
docker exec --user root moodle-app \
  chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics

docker exec --user root moodle-app \
  chmod -R 755 /bitnami/moodle/blocks/gitmetrics
```

### PASO 5 — Instalar el plugin en Moodle

```bash
docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/upgrade.php --non-interactive
```

Debes ver al final:

```
-->block_gitmetrics
++ Success ...
```

### PASO 6 — Abrir Moodle y añadir el bloque

1. Abre `http://localhost:8000`
2. Inicia sesión: usuario `admin`, contraseña `adminpass123`
3. Entra en un curso → **Activar edición** → **Añadir un bloque** → **Métricas de Base de Conocimiento Git**
4. Haz clic en el engranaje del bloque → **Configurar**
5. Pega la URL del repositorio: `https://github.com/julia8873/bdc-prueba`
6. Guarda → las métricas aparecen automáticamente

---

## Credenciales por defecto

| Servicio | URL | Usuario | Contraseña |
|---|---|---|---|
| Moodle | `http://localhost:8000` | `admin` | `adminpass123` |
| Element Web | `http://localhost:8081` | `admin` | `adminpass123` |
| MariaDB | `localhost:3306` (solo interno) | `bn_moodle` | `moodle_db_pass` |

---

## Documentación detallada

- **Plugin `gitmetrics`** → [`gitmetrics/README.md`](./gitmetrics/README.md)
  - Estructura del plugin, comandos de diagnóstico, métricas calculadas y opciones avanzadas
- **Entorno Docker** → [`moodle-matrix-dev/README.md`](./moodle-matrix-dev/README.md)
  - Configuración de Matrix, Ollama y servicios adicionales
