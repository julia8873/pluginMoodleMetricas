# pluginMoodleMetricas — Plataforma de Evaluación de Bases de Conocimiento e Integración con Matrix en Moodle

Entorno integral de Moodle (`block_gitmetrics`) y comunicación colaborativa que analiza repositorios de **GitHub y GitLab** bajo el estándar **OKF (Open Knowledge Framework)** e integra salas de chat **Matrix (Synapse & Element)** sincronizadas nativamente con cada asignatura del LMS.

---

## 📋 Índice de Contenidos

1. [Componentes del Proyecto](#1-componentes-del-proyecto)
2. [Requisitos Previos](#2-requisitos-previos)
3. [Guía de Instalación Paso a Paso](#3-guía-de-instalación-paso-a-paso)
   - [Opción A: Instalación Automática (Recomendada)](#opción-a-instalación-automática-recomendada)
   - [Opción B: Instalación Manual Paso a Paso](#opción-b-instalación-manual-paso-a-paso)
4. [Guía de Uso en Moodle y Exploración de Documentos](#4-guía-de-uso-en-moodle-y-exploración-de-documentos)
   - [Acceso al Curso Dedicado: Panel de Métricas y BdC](#acceso-al-curso-dedicado-panel-de-métricas-y-bdc)
   - [Explorador de Documentos y Buscador Instantáneo](#explorador-de-documentos-y-buscador-instantáneo)
   - [Visor Markdown en Vivo con Metadatos YAML y Wiki-links](#visor-markdown-en-vivo-con-metadatos-yaml-y-wiki-links)
   - [Secciones Cuantitativas y Pestañas en Asignaturas](#secciones-cuantitativas-y-pestañas-en-asignaturas)
5. [Guía de Apertura e Integración con Matrix y el Bot de GitHub](#5-guía-de-apertura-e-integración-con-matrix-y-el-bot-de-github)
   - [Apertura de Element Web (Matrix) y Synapse](#apertura-de-element-web-matrix-y-synapse)
   - [Paso 1: Crear la Cuenta de Administrador en Matrix](#paso-1-crear-la-cuenta-de-administrador-en-matrix)
   - [Paso 2: Obtener el Access Token en Element Web](#paso-2-obtener-el-access-token-en-element-web)
   - [Paso 3: Activar la Comunicación con Matrix en Moodle](#paso-3-activar-la-comunicación-con-matrix-en-moodle)
   - [Paso 4: Conectar una Sala de Matrix con una Asignatura](#paso-4-conectar-una-sala-de-matrix-con-una-asignatura)
   - [Paso 5: Configurar el Bot Asistente de GitHub (Maubot)](#paso-5-configurar-el-bot-asistente-de-github-maubot)
6. [Configuración de Proveedores Git (GitHub vs GitLab)](#6-configuración-de-proveedores-git-github-vs-gitlab)
7. [Credenciales Rápidas del Entorno](#7-credenciales-rápidas-del-entorno)

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

## 4. Guía de Uso en Moodle y Exploración de Documentos

### Acceso al Curso Dedicado: Panel de Métricas y BdC
Abre `http://localhost:8000` e inicia sesión con `admin` / `adminpass123`. Accede a la tarjeta de curso **Panel de Métricas y BdC**.

### Explorador de Documentos y Buscador Instantáneo
En la sección **`📂 Acceso a Documentos`** de la asignatura:
- **Carpetas Colapsables (`<details>`)**: Los directorios del repositorio (ej. `okf/concepts`, `okf/entities`) se presentan organizados en carpetas desplegables para no abrumar la vista.
- **Buscador en Tiempo Real**: Escribe en la barra de búsqueda `🔍` términos o guiones exactos (`lema-de-gronwall`, `ecuacion`, `concepts`). Las filas no coincidentes se ocultan inmediatamente y se abren solo las carpetas con resultados.
- **Botones `➕ Abrir todas` / `➖ Cerrar todas`**: Controla con un clic la expansión global de toda la jerarquía de ficheros del repositorio remoto.

### Visor Markdown en Vivo con Metadatos YAML y Wiki-links
Al hacer clic sobre cualquier fichero del explorador o sobre el botón `↗`:
- **Lectura en Memoria RAM**: El documento se descarga por API en la memoria RAM en el segundo exacto en que lo abres. **No se almacena en disco de Moodle**, garantizando cero duplicación y datos siempre frescos.
- **Tarjeta YAML (Frontmatter)**: El visor extrae la cabecera `---` y muestra una ficha de colores con el Título, Descripción, Tipos y pastillas de Etiquetas (`tags`).
- **Resolución de `[[wiki-links]]`**: Convierte hipervínculos dobles estilo Obsidian (`[[okf/entities/...]]`) en enlaces de Moodle entre documentos.
- **Botón Remoto (`↗`)**: Abre el fichero en la interfaz externa de GitLab o GitHub.

### Secciones Cuantitativas y Pestañas en Asignaturas
Debajo del explorador se muestran los 4 acordeones estadísticos calculados sobre el repositorio (`Volumen y Tamaño`, `Red de Enlaces y Huérfanos`, `Taxonomía YAML`, y `Calidad Markdown/LaTeX/Tablas`). 
Además, en **cualquier asignatura de tu plataforma**, el plugin añade automáticamente una pestaña superior llamada **`Métricas de Base de Conocimiento Git`** para ver el informe del repositorio a pantalla completa.

---

## 5. Guía de Apertura e Integración con Matrix y el Bot de GitHub

El entorno incluye una solución completa de mensajería instantánea federada que conecta de forma nativa los cursos de Moodle con salas de chat en **Matrix (Synapse)** accesibles mediante el cliente web **Element**.

### Apertura de Element Web (Matrix) y Synapse
- **Cliente Web Element**: Abre en tu navegador `http://localhost:8081`
- **Servidor Homeserver Synapse**: Escucha de forma interna y externa en `http://localhost:8008` (en Docker se comunica con Moodle bajo el nombre de host interno `http://matrix-synapse:8008`).

---

### Paso 1: Crear la Cuenta de Administrador en Matrix
Para inicializar el usuario principal que vinculará Moodle con el servidor Synapse, ejecuta el siguiente comando en tu consola de WSL:

```bash
docker exec -it matrix-synapse register_new_matrix_user \
  -c /data/homeserver.yaml \
  --user admin --password adminpass123 --admin \
  http://localhost:8008
```
*(Si te pide confirmación, escribe `Y` o los datos solicitados. El usuario será `@admin:localhost` y su clave `adminpass123`).*

Una vez creado, entra a **`http://localhost:8081` (Element Web)** e inicia sesión con:
- **Username**: `admin`
- **Password**: `adminpass123`
- **Homeserver URL**: Si no aparece por defecto, indícale `http://localhost:8008`

---

### Paso 2: Obtener el Access Token en Element Web
Para que Moodle pueda crear salas e invitar a profesores/estudiantes de forma automática por API, necesita el token de acceso del administrador:
1. En **Element Web** (`http://localhost:8081`), haz clic en tu avatar o menú de usuario (esquina superior izquierda).
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
     - **URL del servidor Matrix (`Matrix Homeserver URL`)**: `http://matrix-synapse:8008` *(¡Importante! Usar el nombre del contenedor interno de Docker, no `localhost`, para que PHP en Moodle pueda conectar con Synapse por la red Docker)*.
     - **Access Token (`Matrix Access Token`)**: Pega el token de Element Web copiado en el Paso 2.
     - **URL de Element Web (`Element Web URL`)**: `http://localhost:8081`
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

## 6. Configuración de Proveedores Git (GitHub vs GitLab)

| Proveedor | Cuándo Elegirlo | URL del Repositorio | Token Necesario |
| :--- | :--- | :--- | :--- |
| **GitHub** | Proyectos y repos en `github.com`. | `https://github.com/owner/repo` | GitHub Personal Access Token (PAT) clásico con scope `repo` o `public_repo`. Configurable en *Administración del sitio > Plugins > Bloques > Git Knowledge Base Metrics*. |
| **GitLab (OSL / Local / Cloud)** | Servidor de la Oficina de Software Libre (OSL) de tu universidad, laboratorios locales o `gitlab.com`. | `https://gitlab.osl.ugr.es/owner/repo`<br>`http://localhost:8929/owner/repo` | GitLab Access Token (`PRIVATE-TOKEN`) con scope `read_api`. Tolerante a SSL autofirmado (`ignoresecurity => true`). |

---

## 7. Credenciales Rápidas del Entorno

| Servicio | URL Local | Usuario | Contraseña |
| :--- | :--- | :--- | :--- |
| **Moodle 4.2+** | `http://localhost:8000` | `admin` | `adminpass123` |
| **Element Web (Cliente Matrix)** | `http://localhost:8081` | `admin` | `adminpass123` |
| **Maubot (GitHub Bot Manager)** | `http://localhost:29316/_matrix/maubot/` | Ver `config.yaml` | Ver `config.yaml` |
| **MariaDB (Base de datos Moodle)** | Interno en Docker (`localhost:3306`) | `bn_moodle` | `moodle_db_pass` |
