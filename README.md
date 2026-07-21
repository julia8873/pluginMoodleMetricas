# pluginMoodleMetricas — Plataforma de Evaluación de Bases de Conocimiento e Integración con Matrix en Moodle

Entorno integral de Moodle (`block_gitmetrics`) y comunicación colaborativa que analiza repositorios de **GitHub y GitLab** bajo el estándar **OKF (Open Knowledge Framework)** e integra salas de chat **Matrix (Synapse & Element)** sincronizadas nativamente con cada asignatura del LMS.

---

## Índice de Contenidos

1. [Componentes del Proyecto](#1-componentes-del-proyecto)
2. [Requisitos Previos](#2-requisitos-previos)
3. [Guía de Instalación Paso a Paso](#3-guía-de-instalación-paso-a-paso)
   - [Opción A: Instalación Automática (Recomendada)](#opción-a-instalación-automática-recomendada)
   - [Opción B: Instalación Manual Paso a Paso](#opción-b-instalación-manual-paso-a-paso)
4. [Guía de Uso y Resumen de las Secciones de Métricas](#4-guía-de-uso-y-resumen-de-las-secciones-de-métricas)
5. [Integración con Obsidian (Módulo Opcional)](#5-integración-con-obsidian-módulo-opcional)
6. [Guía de Apertura e Integración con Matrix y el Bot de GitHub](#6-guía-de-apertura-e-integración-con-matrix-y-el-bot-de-github)
7. [Configuración de Proveedores Git (GitHub vs GitLab)](#7-configuración-de-proveedores-git-github-vs-gitlab)
8. [Credenciales Rápidas del Entorno](#8-credenciales-rápidas-del-entorno)

---

## 1. Componentes del Proyecto

| Componente | Descripción | Enlace |
| :--- | :--- | :--- |
| **`gitmetrics/`** | Plugin de bloque oficial para Moodle (`block_gitmetrics`). Contiene el motor cuantitativo OKF, el explorador en memoria, la resolución de enlaces `[[wiki-links]]` y los scripts CLI de despliegue. | [`gitmetrics/README.md`](./gitmetrics/README.md) |
| **`moodle-matrix-dev/`** | Stack Docker Compose orquestado que contiene Moodle 4.2+, MariaDB, Synapse (Homeserver Matrix), Element Web (Cliente), Maubot (GitHub Bot) y Ollama (LLM local). | [`moodle-matrix-dev/README.md`](./moodle-matrix-dev/README.md) |
| **`instalar.sh`** | Guion automatizado que inicializa los contenedores, instala y actualiza el plugin, ajusta permisos al demonio web y puebla la asignatura de métricas de un solo golpe. | Ver raíz |

---

## 2. Requisitos Previos

- **Docker Desktop** activo y corriendo en tu máquina local.
- **WSL 2 (Ubuntu)** en sistemas Windows.
- **Git** en `/mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas`.

---

## 3. Guía de Instalación Paso a Paso

### Opción A: Instalación Automática (Recomendada)

Ejecuta el script automatizado que coordina y despliega todo el sistema:

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas
./instalar.sh
```

El script inicia los servicios Docker, espera al servidor web, instala `block_gitmetrics`, realiza la migración de base de datos y genera el curso central de evaluación.

---

### Opción B: Instalación Manual Paso a Paso

1. **Levantar contenedores**:
   ```bash
   cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev
   docker compose up -d
   ```
2. **Esperar a Moodle** verificando los logs hasta `** Moodle setup finished! **`:
   ```bash
   docker compose logs -f moodle
   ```
3. **Copiar y asignar permisos al plugin en el contenedor**:
   ```bash
   docker cp ../gitmetrics moodle-app:/bitnami/moodle/blocks/gitmetrics
   docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics
   docker exec --user root moodle-app chmod -R 755 /bitnami/moodle/blocks/gitmetrics
   ```
4. **Instalar en Base de Datos y Crear Curso**:
   ```bash
   docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/upgrade.php --non-interactive
   docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_course.php
   docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/purge_caches.php
   ```

---

## 4. Guía de Uso y Resumen de las Secciones de Métricas

### Acceso al Curso Dedicado: Panel de Métricas y BdC
Al finalizar la instalación, entra a `http://localhost:8000` con `admin` / `adminpass123` y haz clic en la tarjeta del curso **Panel de Métricas y BdC**. La asignatura está organizada en 5 secciones que proporcionan el siguiente análisis:

- **Sección 0: Acceso a Documentos**
  Proporciona un explorador jerárquico de carpetas y un visor integrado en memoria RAM para consultar apuntes Markdown, metadatos YAML y enlaces internos al estilo Obsidian (`[[wiki-links]]`) directamente en Moodle, sin duplicar ni almacenar archivos físicos en el servidor.

- **Sección 1: Volumen y Tamaño de la Base de Conocimiento**
  Proporciona estadísticas sobre la magnitud y cumplimiento normativo del repositorio: recuento total de archivos `.md`, profundidad de directorios, conteo y promedio de palabras por documento, y verificación automática de ficheros esenciales del marco OKF (`README.md`, `SUMMARY.md`, `LICENSE`, `CONTRIBUTING.md`).

- **Sección 2: Red de Enlaces e Interconectividad Markdown**
  Proporciona un análisis de teoría de grafos del repositorio: recuento de hipervínculos internos, promedio de enlaces por documento, índice de densidad y detección de **notas huérfanas** (documentos aislados en el repositorio que no reciben ni emiten enlaces).

- **Sección 3: Taxonomía, Metadatos y Etiquetas YAML**
  Proporciona un inventario del uso de frontmatter en los apuntes: porcentaje de adopción de cabeceras YAML, tabla de campos utilizados (`title`, `description`, `resource`, etc.) y una nube interactiva con la frecuencia de las etiquetas (`tags`).

- **Sección 4: Calidad Markdown y Elementos Estructurales**
  Proporciona una medición del nivel técnico y enriquecimiento sintáctico del contenido: frecuencia media y conteo total por archivo de fórmulas matemáticas LaTeX (`$$` y `$`), tablas Markdown, bloques de código, encabezados (`H1-H6`) y citas.

---

### Integración con otras Asignaturas en Moodle
- **Pestaña Superior de Curso**: El plugin inyecta automáticamente una pestaña llamada **`Métricas de Base de Conocimiento Git`** en la barra superior de cualquier curso para que el docente pueda ver el informe del repositorio a pantalla completa.
- **Bloque en el Menú Lateral**: Puedes añadir el bloque (`Git Knowledge Base Metrics`) desde `Activar edición -> Añadir un bloque` en cualquier curso y configurarle su propia URL y rama de repositorio.

---

## 5. Integración con Obsidian (Módulo Opcional)

El plugin incluye un módulo completamente opcional para visualizar los documentos de la base de conocimiento directamente en **Obsidian**, la aplicación de escritura y gestión de notas con soporte nativo de `[[wiki-links]]` y grafos de conocimiento.

### Cómo Funciona

1. El script `cli/export_obsidian.php` descarga todos los archivos `.md` del repositorio Git remoto (sin guardarlos en Moodle) y los sincroniza en una carpeta local que actúa como vault de Obsidian.
2. Resuelve los `[[wiki-links]]` de la ruta completa OKF (ej. `[[okf/entities/jose-juan]]`) al formato nativo de Obsidian (ej. `[[jose-juan]]`).
3. Cuando la integración está habilitada, en el explorador de documentos de Moodle aparece el botón **"Obsidian"** junto a cada nota que usa el protocolo `obsidian://` para abrirla directamente en la aplicación de escritorio.

### Paso 1: Instalar Obsidian en el Escritorio

Descarga e instala [Obsidian](https://obsidian.md/download) para Windows, macOS o Linux. Al abrirlo por primera vez, crea un nuevo vault:
- **Nombre del vault**: `OKF-Vault` (o el nombre que quieras, anótalo).
- **Carpeta del vault**: elige o crea la carpeta donde quieres que vivan los documentos exportados (ej. `C:\Users\julia\Documents\OKF-Vault`).

### Paso 2: Configurar el Plugin en Moodle

1. Entra a Moodle como administrador: **Administración del sitio > Plugins > Bloques > Git Knowledge Base Metrics**.
2. En la sección **Integración con Obsidian (opcional)**:
   - Marca **Habilitar integración con Obsidian**.
   - **Ruta local del vault**: escribe la ruta absoluta a la carpeta del vault, por ejemplo:
     - Windows (WSL): `/mnt/c/Users/julia/Documents/OKF-Vault`
     - Linux nativo: `/home/julia/Documents/OKF-Vault`
   - **Nombre del vault**: escribe exactamente el nombre con el que creaste el vault en Obsidian (ej. `OKF-Vault`).
3. Guarda los cambios.

### Paso 3: Exportar el Repositorio al Vault

Ejecuta el script de exportación desde el contenedor Docker:

```bash
# Exportación completa (sincroniza todos los .md del repo al vault local)
docker exec --user daemon moodle-app \
  php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php

# Previsualizar qué archivos se escribirían sin tocar el disco (dry-run)
docker exec --user daemon moodle-app \
  php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php --dry-run

# Sobreescribir la ruta del vault sin cambiar los ajustes del plugin
docker exec --user daemon moodle-app \
  php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php \
  --vault=/mnt/c/Users/julia/Documents/OKF-Vault
```

Para sincronización automática, añade el comando al cron del servidor:

```bash
# Cron: exportar cada hora
0 * * * * docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php
```

### Paso 4: Abrir Notas desde Moodle

Una vez habilitada la integración y exportado el vault, en el explorador de documentos aparecerá el botón **"Obsidian"** al lado de cada nota. Al hacer clic, el navegador envía una URI `obsidian://open?vault=OKF-Vault&file=...` que abre inmediatamente el fichero en la aplicación Obsidian del escritorio, con el grafo de conocimiento y los `[[wiki-links]]` resueltos nativamente.

> **Nota**: El protocolo `obsidian://` solo funciona si Obsidian está instalado en el mismo ordenador donde se está usando el navegador. No funciona desde un servidor remoto sin aplicación local.

### Cómo Desactivar o Eliminar la Integración

- **Desactivación rápida**: desmarcar la casilla *Habilitar integración con Obsidian* en los ajustes del plugin oculta los botones instantáneamente.
- **Eliminación completa**: borrar `classes/obsidian_exporter.php` y `cli/export_obsidian.php`, y eliminar los bloques marcados con `OBSIDIAN_OPTIONAL` en `settings.php` y `cli/setup_course.php`.

---

## 6. Guía de Apertura e Integración con Matrix y el Bot de GitHub

El entorno incluye una solución completa de mensajería instantánea federada que conecta de forma nativa los cursos de Moodle con salas de chat en **Matrix (Synapse)** accesibles mediante el cliente web **Element**.

### Apertura de Element Web (Matrix) y Synapse
- **Cliente Web Element**: Abre en tu navegador `http://localhost:8081`
- **Servidor Homeserver Synapse**: Escucha en `http://localhost:8008` (en Docker se comunica con Moodle bajo el nombre de host interno `http://matrix-synapse:8008`).

---

### Paso 1: Crear la Cuenta de Administrador en Matrix
Para inicializar el usuario principal que vinculará Moodle con el servidor Synapse, ejecuta el siguiente comando en tu consola de WSL:

```bash
docker exec -it matrix-synapse register_new_matrix_user \
  -c /data/homeserver.yaml \
  --user admin --password adminpass123 --admin \
  http://localhost:8008
```
*(Si te pide confirmación, escribe `Y`. El usuario será `@admin:localhost` y su clave `adminpass123`).*

Una vez creado, entra a **`http://localhost:8081` (Element Web)** e inicia sesión con:
- **Username**: `admin`
- **Password**: `adminpass123`
- **Homeserver URL**: Si no aparece por defecto, indícale `http://localhost:8008`

---

### Paso 2: Obtener el Access Token en Element Web
Para que Moodle pueda crear salas e invitar a profesores/estudiantes de forma automática por API, necesita el token de acceso del administrador:
1. En **Element Web** (`http://localhost:8081`), haz clic en tu avatar o menú de usuario.
2. Selecciona **All settings (Todos los ajustes)**.
3. Ve a la pestaña **Help & About (Ayuda y Acerca de)**.
4. Despliega la sección **Advanced (Avanzado)** al final.
5. Copia el valor de **Access Token** (un texto largo que empieza por `syd_...` o similar).

---

### Paso 3: Activar la Comunicación con Matrix en Moodle
Ahora vincularemos el LMS Moodle con el Homeserver Matrix:

1. Entra a Moodle (`http://localhost:8000`) como administrador (`admin` / `adminpass123`).
2. **Activar Comunicaciones**:
   - Ve a **Administración del sitio > Desarrollo > Características experimentales (`Experimental settings`)**.
   - Marca la casilla **Habilitar proveedores de comunicación (`Enable communication providers` / `enablecommunication`)**.
   - Guarda los cambios al final de la página.
3. **Configurar el Proveedor Matrix**:
   - Ve a **Administración del sitio > Plugins > Comunicación (`Communication`) > Matrix**.
   - Completa los siguientes parámetros exactos:
     - **URL del servidor Matrix**: `http://matrix-synapse:8008` *(Usar el nombre del contenedor interno de Docker, no `localhost`)*.
     - **Access Token**: Pega el token de Element Web copiado en el Paso 2.
     - **URL de Element Web**: `http://localhost:8081`
   - Guarda los cambios.

---

### Paso 4: Conectar una Sala de Matrix con una Asignatura
Una vez configurado el proveedor, cualquier docente puede asociar una sala de chat colaborativa a su asignatura:
1. Entra a un curso (por ejemplo, **`Panel de Métricas y BdC`**).
2. En la barra superior de pestañas del curso, pulsa en **Configuración (`Settings`)**.
3. Despliega la sección inferior **Comunicación (`Communication`)**.
4. En **Proveedor de comunicación (`Communication provider`)**, selecciona **`Matrix`**.
5. Escribe un nombre para la sala (ej. `Chat de Evaluación de Apuntes OKF`).
6. Guarda los cambios.

> **Nota:** Moodle procesa y crea la sala de Matrix mediante sus tareas programadas en segundo plano (`cron`). Tras la sincronización del cron, dentro del curso aparecerá un enlace directo para abrir **Element Web** y chatear con los miembros matriculados en tiempo real.

---

### Paso 5: Configurar el Bot Asistente de GitHub (Maubot)
El stack incluye **Maubot**, un servicio que ejecuta un bot inteligente en Matrix (`dev.julia.githubbot`) para interactuar con repositorios de GitHub/GitLab directamente desde el chat:

1. **Crear fichero de configuración inicial (si no existe)**:
   ```bash
   cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev
   cp github-bot-plugin/maubot-data/config.yaml.example github-bot-plugin/maubot-data/config.yaml
   ```
2. **Acceso al Panel Web de Maubot**:
   - Abre `http://localhost:29316/_matrix/maubot/`
   - Inicia sesión con el usuario `admin` y la contraseña especificada en `config.yaml`.
3. **Puesta en marcha del Bot**:
   - Ve a **Clients** -> crea una cuenta cliente en Matrix para que el bot pueda unirse a las salas.
   - Ve a **Instances** -> crea una instancia del plugin `dev.julia.githubbot` y vincúlala al cliente.
   - En la configuración de la instancia (`base-config.yaml`), rellena tu `github_token` o claves de LLM (ej. de Ollama en `http://localhost:11434`) si deseas asistencia por inteligencia artificial dentro del chat.
   - El bot recompilará su código en cada reinicio (`docker compose restart maubot`).

---

## 7. Configuración de Proveedores Git (GitHub vs GitLab)

| Proveedor | Cuándo Elegirlo | URL del Repositorio | Token Necesario |
| :--- | :--- | :--- | :--- |
| **GitHub** | Proyectos y repos en `github.com`. | `https://github.com/owner/repo` | GitHub Personal Access Token (PAT) clásico con scope `repo` o `public_repo`. Configurable en *Administración del sitio > Plugins > Bloques > Git Knowledge Base Metrics*. |
| **GitLab (OSL / Local / Cloud)** | Servidor de la Oficina de Software Libre (OSL) de tu universidad, laboratorios locales o `gitlab.com`. | `https://gitlab.osl.ugr.es/owner/repo`<br>`http://localhost:8929/owner/repo` | GitLab Access Token (`PRIVATE-TOKEN`) con scope `read_api`. Tolerante a SSL autofirmado (`ignoresecurity => true`). |

---

## 8. Credenciales Rápidas del Entorno

| Servicio | URL Local | Usuario | Contraseña |
| :--- | :--- | :--- | :--- |
| **Moodle 4.2+** | `http://localhost:8000` | `admin` | `adminpass123` |
| **Element Web (Cliente Matrix)** | `http://localhost:8081` | `admin` | `adminpass123` |
| **Maubot (GitHub Bot Manager)** | `http://localhost:29316/_matrix/maubot/` | Ver `config.yaml` | Ver `config.yaml` |
| **MariaDB (Base de datos Moodle)** | Interno en Docker (`localhost:3306`) | `bn_moodle` | `moodle_db_pass` |
