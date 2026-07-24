# Local Moodle & Matrix Dev/Testing Stack

Stack Docker Compose para desarrollo y pruebas local de la integración de Moodle con Matrix, incluyendo un bot inteligente de GitHub.

## Servicios

| Servicio | URL local | Descripción |
|---|---|---|
| **Moodle** | `http://localhost:8000` | LMS (Bitnami Moodle) |
| **MariaDB** | — | Base de datos de Moodle |
| **Synapse** | `http://localhost:8008` | Servidor Matrix (homeserver) |
| **Element Web** | `http://localhost:8081` | Cliente web de Matrix |
| **Maubot** | `http://localhost:29316` | Bot de Matrix (GitHub Bot) |
| **Ollama** | `http://localhost:11434` | LLM local (opcional) |

---

## Quick Start

### 1. Configurar maubot

Antes de levantar los servicios, crea el fichero de configuración de maubot:

```bash
cp github-bot-plugin/maubot-data/config.yaml.example github-bot-plugin/maubot-data/config.yaml
```

Edita `config.yaml` para configurar tu usuario y contraseña (en la sección `admins`).

### 2. Levantar los servicios

```bash
docker compose up -d
```

> **Nota:** El primer arranque de Moodle puede tardar 1–2 minutos mientras inicializa la base de datos. El contenedor `maubot` compilará automáticamente el plugin (`.mbp`) desde el código fuente en cada inicio.

<a id="matrix"></a>
## Integración con Matrix y el Bot Git

> **Nota:** Los pasos **8a** y **8b** se realizan automáticamente al ejecutar `instalar.sh`. Solo necesitas ejecutarlos manualmente si realizas la instalación paso a paso (Opción B) o si necesitas reconfigurar el entorno.

---

### Crear el usuario administrador de Matrix

Crear la cuenta de administrador en el servidor Synapse. **`instalar.sh` lo ejecuta automáticamente** como parte del despliegue. Para hacerlo manualmente:

```bash
docker exec -it matrix-synapse register_new_matrix_user \
  -c /data/homeserver.yaml \
  --user admin --password adminpass123 --admin \
  http://localhost:8008
```

---

### Conectar Moodle con Matrix

Conectar el plugin de Moodle con el servidor Synapse para permitir la comunicación entre ambos. Existen dos formas de hacerlo:

#### Alternativa 1: Configuración automática (script)

Activa el subsistema de comunicaciones, desbloquea los puertos internos Docker en las reglas cURL de Moodle, obtiene el Access Token de Synapse automáticamente y guarda todo en la base de datos. **`instalar.sh` lo ejecuta automáticamente.** Para lanzarlo de forma aislada:

```bash
docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_matrix.php
```

#### Alternativa 2: Configuración manual (web)

Configurar manualmente desde la interfaz web de Moodle:

1. **Administración del sitio → Desarrollo → Características experimentales** → activar **Habilitar proveedores de comunicación**.
2. **Administración del sitio → Seguridad → Seguridad HTTP** → añadir puertos `80`, `443`, `8008`, `8081` a la lista de puertos permitidos y vaciar la lista de hosts bloqueados.
3. **Administración del sitio → Plugins → Comunicación → Matrix** y configurar:
   - **URL del servidor**: `http://matrix-synapse:8008` *(nombre interno Docker, no `localhost`)*
   - **Access Token**: copiar desde Element Web (`http://localhost:8081`) → Configuración → Help & About → Advanced
   - **URL de Element Web**: `http://localhost:8081`

---

### Las salas de chat (Automatización y Desactivación)

Cada vez que creas una asignatura nueva en Moodle, se genera y vincula automáticamente una sala de chat en Matrix (con el bot).

Si un profesor no desea tener el chat activo para su asignatura, puede **deshabilitarlo manualmente** (Opt-out):
1. En la asignatura, ve a la barra superior → **Más... → Comunicación**.
2. Selecciona **Ninguno** en el proveedor de comunicación y pulsa guardar.

*Nota: Si acabas de crear el curso y el chat aún no aparece en Element, puedes ejecutar el cron para que se genere:* 

```bash
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/cron.php
```

---

### Comandos del bot en la sala Matrix

| Comando | Descripción |
|:---|:---|
| `!ficheros` | Lista el árbol completo del repositorio |
| `!documento <nombre>` | Muestra el contenido y el historial de commits de un fichero |
| `!estudio` | Inicia una sesión de estudio guiado por LLM con preguntas de comprensión |
| `!repaso` | Repaso de conceptos previamente estudiados |
| `!organizacion` | Analiza y propone reorganizaciones de la estructura OKF |
| Adjuntar `.md` / PDF / imagen | Ingesta automática en OKF (si `ingest_automatico: true` en `base-config.yaml`) |

---

---

<a id="git"></a>
## Configuración de Proveedores Git

### GitLab

**Token necesario**: Personal Access Token con permiso `api` (o `read_api` + `write_repository`).

Editar `moodle-matrix-dev/github-bot-plugin/github-bot-plugin/base-config.yaml`:

```yaml
provider: "gitlab"
repo_url: "https://gitlab.com/julia8873/BdC"
gitlab_url: "https://gitlab.com"
gitlab_token: "glpat-xxxxxxxxxxxxxxxx"
github_token: ""
default_owner: "julia8873"
default_repo: "BdC"
default_branch: "main"
```

En Moodle admin → **Plugins → Bloques → Git Knowledge Base Metrics**:
- Proveedor: `GitLab`
- URL Base de GitLab: `https://gitlab.com`
- Token de API: `glpat-...`

### GitHub

**Token necesario**: Personal Access Token (classic) con permiso `repo`.

Editar `base-config.yaml`:

```yaml
provider: "github"
repo_url: "https://github.com/julia8873/BdC"
gitlab_token: ""
github_token: "ghp_xxxxxxxxxxxxxxxx"
default_owner: "julia8873"
default_repo: "BdC"
default_branch: "main"
```

En Moodle admin → **Plugins → Bloques → Git Knowledge Base Metrics**:
- Proveedor: `GitHub`
- Token de API: `ghp_...`

Tras modificar `base-config.yaml` manualmente, reiniciar el bot:

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev
docker compose restart maubot
```

---

---

<a id="docker"></a>
## Gestión de Contenedores Docker

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev

# Arrancar todos los servicios
docker compose up -d

# Detener todos los servicios (conserva los datos)
docker compose down

# Ver estado de los contenedores
docker compose ps

# Ver logs de un servicio concreto
docker compose logs -f moodle
docker compose logs -f maubot
docker compose logs -f synapse

# Reiniciar un servicio individual
docker compose restart maubot

# Actualizar el plugin sin reinstalar el entorno
docker cp ../gitmetrics/. moodle-app:/bitnami/moodle/blocks/gitmetrics/
docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/upgrade.php --non-interactive
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/purge_caches.php

# Acceder a la shell del contenedor Moodle
docker exec -it --user daemon moodle-app bash

# Resetear completamente el entorno (borra todos los datos)
docker compose down -v
```