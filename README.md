# pluginMoodleMetricas - Plataforma de Evaluación de Bases de Conocimiento e Integración con Matrix en Moodle

Entorno integral formado por el plugin de bloque Moodle **`block_gitmetrics`** y un stack de comunicación colaborativa que analiza repositorios de **GitHub y GitLab** bajo el estándar **OKF (Open Knowledge Framework)** e integra salas de chat **Matrix (Synapse + Element)** sincronizadas nativamente con cada asignatura del LMS.

### Diagramas
---

**Diagrama de Arquitectura:**

![Diagrama de Arquitectura del Entorno Integral](./imagenes/arquitectura.png)

**Diagrama de Interacción:**

![Diagrama de Interacción entre los componentes del Entorno Integral](./imagenes/interaccion.png)


---

## Índice de Contenidos

1. [Arquitectura General](#1-arquitectura-general)
2. [Inventario Completo de Ficheros](#2-inventario-completo-de-ficheros)
   - [Raíz del Proyecto](#raíz-del-proyecto)
   - [gitmetrics/ — Plugin Moodle block_gitmetrics](#gitmetrics--plugin-moodle-block_gitmetrics)
   - [moodle-matrix-dev/ — Stack Docker](#moodle-matrix-dev--stack-docker)
3. [Requisitos Previos](#3-requisitos-previos)
4. [Despliegue en Producción](#4-despliegue-en-producción)
   - [Opción A: Instalación Automática (Recomendada)](#opción-a-instalación-automática-recomendada)
   - [Opción B: Instalación Manual Paso a Paso](#opción-b-instalación-manual-paso-a-paso)
5. [Cambiar o Reconectar el Repositorio Git](#5-cambiar-o-reconectar-el-repositorio-git)
6. [Guía de Uso: Secciones de Métricas](#6-guía-de-uso-secciones-de-métricas)
7. [Integración con Matrix y el Bot Git](#7-integración-con-matrix-y-el-bot-git)
8. [Integración con Obsidian (Opcional)](#8-integración-con-obsidian-opcional)
9. [Configuración de Proveedores Git](#9-configuración-de-proveedores-git)
10. [Credenciales del Entorno](#10-credenciales-del-entorno)
11. [Gestión de Contenedores Docker](#11-gestión-de-contenedores-docker)
12. [Seguridad: Gestión de Credenciales](#12-seguridad-gestión-de-credenciales)

---

## 1. Arquitectura General

```
pluginMoodleMetricas/
├── instalar.sh              ← Script para el despliegue
├── configurar_git.sh        ← Script para el cambio de
                                 repositorio Git
├── gitmetrics/              ← Plugin PHP para Moodle
                                 (block_gitmetrics)
└── moodle-matrix-dev/       ← Stack Docker con servicios
    ├── docker-compose.yml   ← Define los contenedores
    ├── synapse-data/        ← Datos persistentes
    ├── github-bot-plugin/   ← Bot de Matrix (Maubot)
    └── usuarios/            ← Scripts CLI de gestión de 
                                 usuarios Moodle
```

**Contenedores Docker del stack:**

| Contenedor | Imagen | Puerto | Función |
|:---|:---|:---|:---|
| `moodle-app` | `bitnamilegacy/moodle:latest` | `8000` | LMS Moodle 4.2+ con el plugin instalado |
| `moodle-mariadb` | `mariadb:10.11` | `3306` (interno) | Base de datos relacional de Moodle |
| `matrix-synapse` | `matrixdotorg/synapse:latest` | `8008` | Homeserver Matrix federado |
| `element-web` | `vectorim/element-web:latest` | `8081` | Cliente web Matrix |
| `maubot` | Custom (`Dockerfile.maubot`) | `29316` | Bot de Matrix con integración Git |
| `ollama` | `ollama/ollama:latest` | `11434` | LLM local para asistencia del bot |

---

## 2. Información sobre cada directorio

- **`Raíz del proyecto (/)`**: Contiene los scripts principales de despliegue (`instalar.sh` y `configurar_git.sh`). Son los encargados de levantar toda la infraestructura de contenedores, configurar las conexiones de repositorios e inicializar los servicios.
- **`gitmetrics/`**: Es el código fuente del plugin de Moodle (`block_gitmetrics`). Aquí se aloja la lógica en PHP para extraer métricas de GitHub/GitLab, procesar los documentos Markdown bajo el estándar OKF y mostrar las estadísticas.
- **`moodle-matrix-dev/`**: Contiene el fichero de Docker Compose que enlaza Moodle con el servidor de chat, además de los siguientes subdirectorios:
  - **`synapse-data/`**: Carpeta donde se guardan de forma permanente los datos, archivos y base de datos del servidor Matrix.
  - **`github-bot-plugin/`**: Contiene el código y la configuración del bot Maubot.
  - **`usuarios/`**: Para gestionar usuarios de Moodle usando la línea de comandos.
---
## 3. Requisitos Previos

| Requisito | Versión mínima | Notas |
|:---|:---|:---|
| **Docker Desktop** | 4.x+ | Debe estar activo con el motor Docker en ejecución |
| **WSL 2 (Ubuntu)** | Ubuntu 20.04+ | Solo en Windows. Los scripts `.sh` se ejecutan en WSL |
| **Python 3** | 3.8+ | Necesario en el host para que `configurar_git.sh` edite el YAML |
| **Git** | 2.x+ | Para clonar el repositorio |
| **Bash** | 4.x+ | Para ejecutar `instalar.sh` y `configurar_git.sh` |

> **IMPORTANTE**: En Windows, todos los comandos `bash` y `docker` se deben ejecutar desde una terminal **WSL 2 (Ubuntu)**, no desde PowerShell ni CMD.

---

## 4. Instalación

### Opción A: Instalación Automática (Recomendada)

Clona el repositorio y ejecuta el script de instalación desde WSL (Ubuntu) indicando la URL y el token de acceso a tu repositorio Git:

```bash
# Acceder al directorio del proyecto en WSL
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas

# Despliegue completo con GitLab
./instalar.sh --url="https://gitlab.com/tu-usuario/tu-repo" --token="glpat-xxxxxxxxxxxxxxxx"

# Despliegue completo con GitHub
./instalar.sh --url="https://github.com/tu-usuario/tu-repo" --token="ghp_xxxxxxxxxxxxxxxx"

# Despliegue sin repositorio (métricas inactivas hasta configurarlas manualmente)
./instalar.sh
```

El script realiza automáticamente estos 8 pasos:

1. Levanta los contenedores Docker (`docker compose up -d`)
2. Espera a que Moodle esté operativo (polling con reintentos)
3. Copia el plugin `gitmetrics/` al contenedor `moodle-app`
4. Ajusta permisos del plugin y del volumen Obsidian
5. Instala/actualiza el plugin en la BD de Moodle (`upgrade.php`)
6. Crea la asignatura "Panel de Métricas y BdC"
7. Configura la integración Matrix (Synapse + Element)
8. Sincroniza el repositorio Git y habilita la integración Obsidian

Al finalizar, el entorno estará accesible en:

```
Moodle:   http://localhost:8000   → Usuario: admin
                                    Contraseña: adminpass123
Matrix:   http://localhost:8081   → Usuario: admin
                                    Contraseña: adminpass123
Maubot:   http://localhost:29316/_matrix/maubot/
```

---

### Opción B: Instalación Manual Paso a Paso

```bash
# 1. Levantar contenedores
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev
docker compose up -d

# 2. Esperar a Moodle (ver logs hasta "** Moodle setup finished! **")
docker compose logs -f moodle

# 3. Copiar el plugin al contenedor
docker cp ../gitmetrics moodle-app:/bitnami/moodle/blocks/gitmetrics

# 4. Ajustar permisos
docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics
docker exec --user root moodle-app chmod -R 755 /bitnami/moodle/blocks/gitmetrics

# 5. Registrar el plugin en la BD de Moodle
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/upgrade.php --non-interactive

# 6. Crear la asignatura dedicada
docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_course.php

# 7. Configurar Matrix
docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_matrix.php

# 8. Limpiar cachés
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/purge_caches.php
```

---

## 5. Cambiar o Reconectar el Repositorio Git

Para cambiar el repositorio (nueva URL, nuevo token, otra rama o pasar de GitLab a GitHub) sin reinstalar nada:

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas

# Sintaxis completa
./configurar_git.sh --url="<URL>" --token="<TOKEN>" --branch="<RAMA>"

# Ejemplo con GitLab (rama main por defecto)
./configurar_git.sh --url="https://gitlab.com/julia8873/BdC" --token="glpat-xxxxxxxxxxxxxxxx"

# Ejemplo con GitHub, rama específica
./configurar_git.sh --url="https://github.com/julia8873/BdC" --token="ghp_xxxxxxxxxxxxxxxx" --branch="develop"

# Modo interactivo (sin argumentos, solicita URL y token)
./configurar_git.sh
```

Este único comando actualiza simultáneamente:
- `base-config.yaml` del bot Maubot (fichero en disco)
- BD interna de Maubot (SQLite dentro del contenedor)
- Contenedor `maubot` (reinicio automático)
- Configuración de Moodle (`mdl_config_plugins`)
- Integración con Obsidian

---

## 6. Guía de Uso: Secciones de Métricas

Accede a `http://localhost:8000` → curso **Panel de Métricas y BdC**. El panel está organizado en 5 secciones:

| Sección | Título | Contenido |
|:---|:---|:---|
| **0** | Acceso a Documentos | Explorador jerárquico de carpetas y visor Markdown en memoria RAM. Soporta `[[wiki-links]]`, LaTeX, tablas y código. Sin almacenamiento local de ficheros. |
| **1** | Volumen y Tamaño de la BdC | Recuento de `.md`, profundidad de directorios, estadísticas de palabras, verificación de ficheros OKF obligatorios (`README.md`, `SUMMARY.md`, `LICENSE`, `CONTRIBUTING.md`). |
| **2** | Red de Enlaces e Interconectividad | Análisis de grafos: recuento de `[[wiki-links]]`, densidad de interconexión, detección de notas huérfanas (sin enlaces entrantes ni salientes). |
| **3** | Taxonomía, Metadatos y Etiquetas YAML | Porcentaje de adopción de frontmatter YAML, tabla de campos usados (`title`, `description`, `resource`, etc.), nube de etiquetas `tags`. |
| **4** | Calidad Markdown y Elementos Estructurales | Frecuencia de fórmulas LaTeX (`$`/`$$`), tablas Markdown, bloques de código, encabezados H1–H6 y citas por documento. |

El plugin también inyecta la pestaña **"Métricas de Base de Conocimiento Git"** en la barra superior de cualquier curso, accesible a pantalla completa desde cualquier asignatura de Moodle.

---

## 7. Integración con Matrix y el Bot Git

> **Nota:** Los pasos **7a** y **7b** se realizan automáticamente al ejecutar `instalar.sh`. Solo necesitas ejecutarlos manualmente si realizas la instalación paso a paso (Opción B) o si necesitas reconfigurar el entorno.

---

### 7a. Crear el usuario administrador de Matrix

Crear la cuenta de administrador en el servidor Synapse. **`instalar.sh` lo ejecuta automáticamente** como parte del despliegue. Para hacerlo manualmente:

```bash
docker exec -it matrix-synapse register_new_matrix_user \
  -c /data/homeserver.yaml \
  --user admin --password adminpass123 --admin \
  http://localhost:8008
```

---

### 7b. Conectar Moodle con Matrix

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

### 7c. Las salas de chat (Automatización y Desactivación)

Cada vez que creas una asignatura nueva en Moodle, se genera y vincula automáticamente una sala de chat en Matrix (con el bot).

Si un profesor no desea tener el chat activo para su asignatura, puede **deshabilitarlo manualmente** (Opt-out):
1. En la asignatura, ve a la barra superior → **Más... → Comunicación**.
2. Selecciona **Ninguno** en el proveedor de comunicación y pulsa guardar.

*Nota: Si acabas de crear el curso y el chat aún no aparece en Element, puedes ejecutar el cron para que se genere:* 

```bash
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/cron.php
```

---

### 7d. Comandos del bot en la sala Matrix

| Comando | Descripción |
|:---|:---|
| `!ficheros` | Lista el árbol completo del repositorio |
| `!documento <nombre>` | Muestra el contenido y el historial de commits de un fichero |
| `!estudio` | Inicia una sesión de estudio guiado por LLM con preguntas de comprensión |
| `!repaso` | Repaso de conceptos previamente estudiados |
| `!organizacion` | Analiza y propone reorganizaciones de la estructura OKF |
| Adjuntar `.md` / PDF / imagen | Ingesta automática en OKF (si `ingest_automatico: true` en `base-config.yaml`) |

---

## 8. Integración con Obsidian (Opcional)

### Configuración previa

1. Editar `moodle-matrix-dev/.env` y definir la ruta del vault en el host:
   ```
   OBSIDIAN_VAULT_PATH=/mnt/c/Users/julia/Documents/OKF-Vault
   ```
2. En Moodle admin → **Plugins → Bloques → Git Knowledge Base Metrics**:
   - Marcar **Habilitar integración con Obsidian**
   - **Ruta local del vault**: `/mnt/c/Users/julia/Documents/OKF-Vault`
   - **Nombre del vault**: `OKF-Vault`

### Sincronización manual

```bash
# Exportar el repositorio al vault
docker exec --user daemon moodle-app \
  php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php

# Modo dry-run (previsualiza sin escribir)
docker exec --user daemon moodle-app \
  php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php --dry-run

# Especificar ruta de vault directamente
docker exec --user daemon moodle-app \
  php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php \
  --vault=/mnt/c/Users/julia/Documents/OKF-Vault
```

### Sincronización automática

La tarea programada `sync_obsidian` se ejecuta cada hora. Para lanzarla manualmente:

```bash
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/cron.php
```

Para programarla en el cron del sistema Linux/WSL (`crontab -e`):

```bash
0 * * * * docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php >/dev/null 2>&1
```

> **Nota**: El protocolo `obsidian://` solo funciona si Obsidian está instalado en el mismo equipo desde el que se usa el navegador. No funciona en acceso remoto.

---

## 9. Configuración de Proveedores Git

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

## 10. Credenciales del Entorno

| Servicio | URL | Usuario | Contraseña |
|:---|:---|:---|:---|
| **Moodle 4.2+** | `http://localhost:8000` | `admin` | `adminpass123` |
| **Element Web (Matrix)** | `http://localhost:8081` | `admin` | `adminpass123` |
| **Maubot (Bot Manager)** | `http://localhost:29316/_matrix/maubot/` | Ver `maubot-data/config.yaml` | Ver `maubot-data/config.yaml` |
| **MariaDB (Moodle DB)** | Interno Docker (`moodle-mariadb:3306`) | `bn_moodle` | `moodle_db_pass` |
| **Synapse Homeserver** | `http://localhost:8008` | — | — |
| **Ollama (LLM local)** | `http://localhost:11434` | — | — |

> **ADVERTENCIA**: Cambiar las credenciales por defecto antes de exponer el entorno en una red distinta a `localhost`. Las contraseñas por defecto son para desarrollo y despliegue local únicamente.

---

## 11. Gestión de Contenedores Docker

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

---

## 12. Seguridad: Gestión de Credenciales

Este proyecto utiliza un sistema de **ficheros plantilla (`.example`)** para evitar que contraseñas, tokens y claves criptográficas se suban al repositorio Git.

### Cómo funciona

Cada fichero que contiene credenciales tiene una versión `.example` con valores de ejemplo. Los ficheros reales (con tus credenciales) están excluidos del repositorio mediante `.gitignore`.

| Fichero real (excluido de Git) | Plantilla versionada (`.example`) |
|:---|:---|
| `moodle-matrix-dev/.env` | `.env.example` |
| `moodle-matrix-dev/synapse-data/homeserver.yaml` | `homeserver.yaml.example` |
| `moodle-matrix-dev/github-bot-plugin/github-bot-plugin/base-config.yaml` | `base-config.yaml.example` |
| `moodle-matrix-dev/github-bot-plugin/maubot-data/config.yaml` | `config.yaml.example` |

### Primer uso (tras clonar el repositorio)

`instalar.sh` **copia automáticamente** cada plantilla `.example` a su fichero real la primera vez que se ejecuta. Si el fichero real ya existe, no lo sobrescribe (para no perder credenciales que ya hayas configurado).

Si prefieres hacerlo manualmente antes de ejecutar `instalar.sh`:

```bash
# Desde la raíz del proyecto
cp moodle-matrix-dev/.env.example moodle-matrix-dev/.env
cp moodle-matrix-dev/synapse-data/homeserver.yaml.example moodle-matrix-dev/synapse-data/homeserver.yaml
cp moodle-matrix-dev/github-bot-plugin/github-bot-plugin/base-config.yaml.example moodle-matrix-dev/github-bot-plugin/github-bot-plugin/base-config.yaml
cp moodle-matrix-dev/github-bot-plugin/maubot-data/config.yaml.example moodle-matrix-dev/github-bot-plugin/maubot-data/config.yaml
```

Después, edita cada fichero y sustituye los valores de ejemplo (`TU_TOKEN_AQUI`, `GENERA_UN_SECRETO_ALEATORIO_AQUI`, etc.) por tus valores reales.
