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

### Paso 3: Exportar y Sincronizar el Repositorio al Vault

Puedes realizar la sincronización de dos formas (o combinadas): manual/mediante cron del sistema, o mediante la Tarea Programada nativa de Moodle.

#### Opción A: Tarea Programada Nativa de Moodle (Recomendado)
El plugin incluye la tarea programada `\block_gitmetrics\task\sync_obsidian` registrada automáticamente en Moodle.
1. Entra a **Administración del sitio > Servidor > Tareas programadas**.
2. Busca **Sincronización programada del vault de Obsidian** (`block_gitmetrics\task\sync_obsidian`).
3. Por defecto está programada para ejecutarse en el minuto 0 de cada hora (`0 * * * *`). Puedes cambiar su periodicidad o ejecutarla manualmente desde la web pulsando el botón **Ejecutar ahora**.
4. Cada vez que el cron general de Moodle se ejecuta (`php admin/cli/cron.php`), esta tarea sincronizará automáticamente las notas al vault configurado.

#### Opción B: Ejecución CLI por Comando o Cron de Sistema Linux
Puedes lanzar la exportación manualmente o integrarla en el cron del sistema operativo:

```bash
# Exportación manual desde el contenedor Docker
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

Para programarlo en el cron de Linux/WSL (`crontab -e`):
```bash
# Ejecutar cada hora exacta en el host
0 * * * * docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php >/dev/null 2>&1
```

### Paso 4: Abrir Notas desde Moodle

Una vez habilitada la integración (`obsidian_enabled`) y exportado el vault, el botón **"Obsidian"** aparecerá en dos ubicaciones estratégicas:
1. **En la Sección 0 (Acceso a Documentos)**: a la derecha de cada fila del explorador jerárquico (`[↗ Ver en GitLab] [Obsidian]`).
2. **En el Visor de Documentos (`view_file.php`)**: en la barra superior derecha de acciones al consultar cualquier apunte.

Al hacer clic, el navegador envía una URI del tipo `obsidian://open?vault=OKF-Vault&file=...` que abre inmediatamente el fichero en la aplicación Obsidian del escritorio, con el grafo de conocimiento y los enlaces internos (`[[wiki-links]]`) resueltos nativamente.

> **Nota**: El protocolo `obsidian://` solo funciona si Obsidian está instalado en el mismo ordenador donde se está usando el navegador. No funciona desde un servidor remoto sin aplicación local.

### Cómo Desactivar o Eliminar la Integración

- **Desactivación rápida**: desmarcar la casilla *Habilitar integración con Obsidian* en los ajustes del plugin oculta los botones instantáneamente y detiene la tarea programada.
- **Eliminación completa**: borrar `classes/obsidian_exporter.php`, `cli/export_obsidian.php` y `classes/task/sync_obsidian.php`, y eliminar los bloques marcados con `OBSIDIAN_OPTIONAL` en `settings.php`, `cli/setup_course.php`, `view_file.php` y `db/tasks.php`.

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

### Paso 3: Activar y Desbloquear la Comunicación con Matrix en Moodle
Ahora vincularemos el LMS Moodle con el Homeserver Matrix y permitiremos las peticiones internas:

1. **Entra a Moodle** (`http://localhost:8000`) como administrador (`admin` / `adminpass123`).
2. **Activar el Subsistema de Comunicaciones**:
   - Ve a **Administración del sitio > Desarrollo > Características experimentales (`Experimental settings`)**.
   - Marca la casilla **Habilitar proveedores de comunicación (`Enable communication providers` / `enablecommunication`)**.
   - Guarda los cambios al final de la página.
3. **Desbloquear Puertos y Red Interna de Docker (Importante para evitar `The URL is blocked`)**:
   Por defecto, la seguridad cURL de Moodle bloquea peticiones a redes privadas y puertos no estándar. Para que Moodle pueda consultar Synapse (`http://matrix-synapse:8008`), ve a **Administración del sitio > Seguridad > Seguridad HTTP**:
   - En **Lista de puertos permitidos (`curlsecurityallowedport`)**, añade los puertos del stack: `443`, `80`, `8008`, `8081` y `8080` (uno por línea).
   - En **Lista de hosts bloqueados (`curlsecurityblockedhosts`)**, elimina o vacía las subredes internas (`172.16.0.0/12`, `127.0.0.0/8`, `localhost`) que impidan a los contenedores hablar entre sí.
   - Guarda los cambios.
4. **Configurar el Proveedor Matrix**:
   - Ve a **Administración del sitio > Plugins > Comunicación (`Communication`) > Matrix**.
   - Completa los siguientes parámetros exactos:
     - **URL del servidor Matrix**: `http://matrix-synapse:8008` *(Usar el nombre del contenedor interno de Docker, no `localhost`)*.
     - **Access Token**: Pega el token de Element Web copiado en el Paso 2 (`@admin:localhost`). *(Nota: Si este campo se deja vacío, Moodle ocultará la opción de Matrix en las asignaturas).*
     - **URL de Element Web**: `http://localhost:8081`
   - Guarda los cambios.

---

### Paso 4: Conectar una Asignatura y Creación Automática de la Sala
En Moodle 4.3+, la configuración de comunicación tiene su propia pestaña dedicada independiente de los ajustes generales del curso. Para asociar una sala y hacer que se cree automáticamente en Synapse:

1. **Acceder a la configuración de Comunicación del Curso**:
   - Entra a la asignatura (por ejemplo, **`Panel de Métricas y BdC`**).
   - En la barra superior horizontal de pestañas del curso (`Curso | Configuración | Participantes | Calificaciones | Más...`), pulsa en **`Más...` -> `Comunicación`** (o en **`Comunicación`** si está visible directamente en la barra).
   - *(Ruta directa: `/communication/configure.php?instanceid=ID_CURSO`)*.
2. **Seleccionar el Proveedor Matrix**:
   - En el menú desplegable **Proveedor (`Provider`)**, selecciona **`Matrix`**.
   - Escribe un nombre identificativo para la sala (ej. `Panel de Métricas y BdC` o `Chat OKF de Asignatura`).
   - Pulsa en **Guardar cambios**.

#### Proceso de Creación Automática en Synapse
Al guardar la configuración, Moodle gestiona la creación de la sala de forma totalmente automática y desatendida mediante su cola de tareas en segundo plano (`Ad-hoc tasks`):
- **Encolado automático**: Moodle crea el registro local en su base de datos (`mdl_communication`) y encola la tarea `\core_communication\task\create_and_configure_room_task`.
- **Ejecución y creación remota**: Cuando se ejecuta el cron del sistema (`php admin/cli/cron.php`), Moodle se conecta a la API REST de Synapse (`_matrix/client/v3/createRoom`), crea la sala de chat privada en Matrix, le asigna el tema y registra su identificador único (`room_id`, por ejemplo `!KVJQNCcFnFgfcpvSfG:localhost`).
- **Sincronización de participantes**: El sistema matriculará de forma progresiva en la sala de Matrix a los profesores y estudiantes inscritos en el curso conforme accedan al entorno.

> **Ejecución inmediata por CLI (Opcional)**: Si no deseas esperar al ciclo regular del cron del servidor para que se genere la sala en Matrix, puedes forzar el procesado instantáneo de las tareas ad-hoc ejecutando este comando desde tu terminal:
> ```bash
> docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/cron.php
> ```
> Una vez completado, dentro del curso aparecerá el enlace directo para abrir **Element Web** (`http://localhost:8081`) y acceder a la sala.

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
