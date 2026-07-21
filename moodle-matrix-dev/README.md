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

Edita `config.yaml` y rellena los campos marcados (`admins`, etc.). El campo `unshared_secret: generate` ya está listo para que maubot genere el secreto automáticamente.

### 2. Levantar los servicios

```bash
docker compose up -d
```

> **Nota:** El primer arranque de Moodle puede tardar 1–2 minutos mientras inicializa la base de datos. El contenedor `maubot` compilará automáticamente el plugin (`.mbp`) desde el código fuente en cada inicio.

### 3. Crear la cuenta de administrador de Matrix

```bash
docker exec -it matrix-synapse register_new_matrix_user \
  -c /data/homeserver.yaml \
  --user admin --password adminpass123 --admin \
  http://localhost:8008
```

Luego inicia sesión en Element Web (`http://localhost:8081`) con `admin` / `adminpass123`.

### 4. Obtener el Access Token de Matrix

1. En Element Web, ve a tu perfil → **All settings**
2. Pestaña **Help & About** → sección **Advanced**
3. Copia el campo **Access Token**

### 5. Activar la comunicación en Moodle

1. Accede a Moodle (`http://localhost:8000`) con `adminMoodle` / `test1234`
2. Navega a: **Site Administration → Development → Experimental → Experimental settings**
3. Activa **Enable communication providers** (`enablecommunication`) y guarda.

### 6. Configurar el proveedor Matrix en Moodle

1. Navega a: **Site Administration → Plugins → Communication → Matrix**
2. Configura:
   - **Matrix Homeserver URL:** `http://matrix-synapse:8008` *(nombre interno de Docker)*
   - **Access Token:** el token copiado en el paso 4
   - **Element Web URL:** `http://localhost:8081`
3. Guarda.

### 7. Activar Matrix en un curso

1. Entra en un curso → **Settings** → sección **Communication**
2. Establece el **Communication provider** a **Matrix** y pon un nombre de sala
3. Guarda. Moodle creará la sala vía tareas cron en segundo plano.

---

## Bot de Matrix Multi-Proveedor (Maubot: GitLab y GitHub)

El bot se compila automáticamente desde el código fuente al levantar el contenedor. El código fuente está en `github-bot-plugin/github-bot-plugin/`. El bot cuenta con una arquitectura modular (`GitProvider`) que soporta indistintamente repositorios en **GitLab** o **GitHub**.

### Paso 1: Configurar el bot tras el primer arranque

1. Accede a la interfaz de Maubot: `http://localhost:29316/_matrix/maubot/`
2. Inicia sesión con las credenciales definidas en `config.yaml` (`admins`)
3. Crea un **Client** (cuenta de Matrix que usará el bot para unirse a las salas)
4. Crea una **Instance** del plugin `dev.julia.githubbot` vinculada a tu cliente.

### Paso 2: Elegir Proveedor Git y Configurar (`base-config.yaml`)

Puedes definir el comportamiento del bot directamente editando el archivo `github-bot-plugin/github-bot-plugin/base-config.yaml` o en el panel de configuración de tu instancia en Maubot:

#### Opción A: Ejecución en GitLab
```yaml
provider: "gitlab"
repo_url: "https://gitlab.com/julia8873/BdC"
gitlab_url: "https://gitlab.com"
gitlab_token: "glpat-xxxxxxxxxxxxxxxx"
default_owner: "julia8873"
default_repo: "BdC"
default_branch: "main"
```
*(El bot utilizará `GitLabClient` con llamadas a la API v4 de GitLab, resolviendo rutas codificadas y transacciones multi-acción para commits).*

#### Opción B: Ejecución en GitHub
```yaml
provider: "github"
repo_url: "https://github.com/julia8873/BdC"
github_token: "ghp_xxxxxxxxxxxxxxxx"
default_owner: "julia8873"
default_repo: "BdC"
default_branch: "main"
```
*(El bot utilizará `GitHubClient` conectándose a `api.github.com`).*

### Paso 3: Reiniciar y Probar

Cada vez que modifiques el archivo de configuración o el código Python, el plugin se recompila y recarga automáticamente al reiniciar el contenedor:

```bash
docker compose restart maubot
```

O bien, reconstruye la imagen si cambiaron las dependencias:

```bash
docker compose up -d --build maubot
```

---

## Utilidades de desarrollo

### Ver logs

```bash
docker compose logs -f moodle
docker compose logs -f synapse
docker compose logs -f maubot
```

### Parar el entorno

```bash
# Parar y conservar datos
docker compose down

# Parar y borrar todos los datos (reset limpio)
docker compose down -v
```
