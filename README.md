# pluginMoodleMetricas — Plataforma de Evaluación y Exploración de Bases de Conocimiento Git para Moodle

Plugin de bloque y entorno integral de Moodle (`block_gitmetrics`) que analiza repositorios de **GitHub y GitLab** (tanto nube como servidores universitarios OSL o locales) estructurados bajo el estándar **OKF (Open Knowledge Framework)**. 

El sistema calcula métricas cuantitativas en tiempo real y ofrece un explorador de documentos interactivo con visor Markdown en memoria RAM (sin almacenar ficheros físicos en Moodle) e interconectividad entre notas estilo Obsidian (`[[wiki-links]]`).

---

## 📋 Índice de Contenidos

1. [Componentes del Proyecto](#1-componentes-del-proyecto)
2. [Requisitos Previos](#2-requisitos-previos)
3. [Guía de Instalación Paso a Paso](#3-guía-de-instalación-paso-a-paso)
   - [Opción A: Instalación Automática (Recomendada)](#opción-a-instalación-automática-recomendada)
   - [Opción B: Instalación Manual Paso a Paso](#opción-b-instalación-manual-paso-a-paso)
4. [Guía de Uso Paso a Paso](#4-guía-de-uso-paso-a-paso)
   - [Acceso al Curso Dedicado: Panel de Métricas y BdC](#acceso-al-curso-dedicado-panel-de-métricas-y-bdc)
   - [Uso del Explorador de Documentos y Buscador (Sección 0)](#uso-del-explorador-de-documentos-y-buscador-sección-0)
   - [Visor Markdown en Vivo con Soporte YAML y Wiki-links](#visor-markdown-en-vivo-con-soporte-yaml-y-wiki-links)
   - [Secciones de Métricas Cuantitativas (Secciones 1 a 4)](#secciones-de-métricas-cuantitativas-secciones-1-a-4)
   - [Uso como Pestaña Superior en Cualquier Asignatura](#uso-como-pestaña-superior-en-cualquier-asignatura)
   - [Uso como Bloque en el Menú Lateral](#uso-como-bloque-en-el-menú-lateral)
5. [Configuración de Proveedores (GitHub vs GitLab)](#5-configuración-de-proveedores-github-vs-gitlab)
6. [Credenciales del Entorno](#6-credenciales-del-entorno)

---

## 1. Componentes del Proyecto

| Componente | Descripción | Enlace |
| :--- | :--- | :--- |
| **`gitmetrics/`** | Plugin de bloque oficial para Moodle (`block_gitmetrics`). Contiene el motor de cálculo de métricas, el explorador de carpetas colapsables, el visor en memoria con parseo YAML/Wiki-links y los scripts CLI. | [`gitmetrics/README.md`](./gitmetrics/README.md) |
| **`moodle-matrix-dev/`** | Entorno Docker local orquestado con Moodle 4.2+, MariaDB, Synapse (Matrix), Element Web y Ollama para desarrollo ágil y autosuficiente. | [`moodle-matrix-dev/README.md`](./moodle-matrix-dev/README.md) |
| **`instalar.sh`** | Script de automatización integral que levanta Docker, espera al servidor Moodle, copia el plugin, asigna permisos daemon, ejecuta migraciones y crea el curso de métricas en un solo paso. | Ver raíz |

---

## 2. Requisitos Previos

Para desplegar y utilizar este entorno en tu equipo local necesitas:
- **Docker Desktop** instalado y en ejecución en tu sistema (Windows/Mac/Linux).
- **WSL 2 (Windows Subsystem for Linux)** con una distribución de Ubuntu (si estás en Windows).
- **Git** instalado dentro de WSL para clonar y gestionar el repositorio en `/mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas`.

---

## 3. Guía de Instalación Paso a Paso

### Opción A: Instalación Automática (Recomendada)

Dispones del script automatizado `instalar.sh` que realiza todo el proceso desde cero sin intervención manual:

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas
./instalar.sh
```

**¿Qué hace exactamente el script?**
1. Levanta los contenedores de Moodle y MariaDB mediante `docker compose up -d`.
2. Sondea el contenedor en bucle hasta que PHP y el servidor Moodle responden correctamente (`OK`).
3. Copia la carpeta `gitmetrics/` al directorio de bloques de Moodle (`/bitnami/moodle/blocks/gitmetrics`).
4. Ajusta los permisos al usuario del servidor web (`daemon:daemon` y `755`).
5. Ejecuta el actualizador de base de datos de Moodle (`upgrade.php --non-interactive`) para registrar el bloque y su tabla de caché.
6. Ejecuta `setup_course.php`, creando la asignatura centralizada **Panel de Métricas y BdC** (ID: 4), matriculando al usuario `admin` y poblando todos los temas.

Al concluir, verás por consola:
```text
------------------------------------------------------------------------------
 ¡TODO LISTO! EL ENTORNO Y EL PLUGIN ESTÁN OPERATIVOS
------------------------------------------------------------------------------
 Moodle URL  : http://localhost:8000
 Usuario     : admin
 Contraseña  : adminpass123
------------------------------------------------------------------------------
```

---

### Opción B: Instalación Manual Paso a Paso

Si prefieres realizar el despliegue de forma manual o paso a paso para depurar:

#### Paso 1: Levantar el entorno Docker
```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev
docker compose up -d
```

#### Paso 2: Verificar que Moodle ha iniciado
Obtén los logs en tiempo real para confirmar que la base de datos y la instalación inicial han terminado:
```bash
docker compose logs -f moodle
```
Espera hasta ver la línea `** Moodle setup finished! **` (o pulsa `Ctrl + C` cuando esté listo).

#### Paso 3: Copiar los ficheros del plugin al contenedor
```bash
docker cp /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/gitmetrics moodle-app:/bitnami/moodle/blocks/gitmetrics
```

#### Paso 4: Configurar los permisos y propiedad
```bash
docker exec --user root moodle-app chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics
docker exec --user root moodle-app chmod -R 755 /bitnami/moodle/blocks/gitmetrics
```

#### Paso 5: Ejecutar la actualización en base de datos
```bash
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/upgrade.php --non-interactive
```

#### Paso 6: Poblar la asignatura central y limpiar caché
```bash
docker exec --user daemon moodle-app php /bitnami/moodle/blocks/gitmetrics/cli/setup_course.php
docker exec --user daemon moodle-app php /bitnami/moodle/admin/cli/purge_caches.php
```

---

## 4. Guía de Uso Paso a Paso

### Acceso al Curso Dedicado: Panel de Métricas y BdC

El sistema crea automáticamente un curso especial que funciona como cuadro de mando de evaluación:
1. Abre tu navegador y entra a `http://localhost:8000`.
2. Inicia sesión con el usuario `admin` y la contraseña `adminpass123`.
3. En la página inicial (`Mis cursos`), haz clic en **Panel de Métricas y BdC**.

---

### Uso del Explorador de Documentos y Buscador (Sección 0)

En la cabecera del curso encontrarás la sección principal titulada **`📂 Acceso a Documentos`**:

- **Carpetas Colapsables (`<details>` / `<summary>`)**: Todos los archivos Markdown (`.md`) del repositorio externo (por ejemplo, `okf/concepts`, `okf/entities`, `okf/sources`, `okf/reports`) están organizados por directorio. Por defecto, las carpetas pequeñas o la raíz están abiertas, y las carpetas extensas están cerradas para una navegación limpia.
- **Barra de Búsqueda Instantánea**:
  - Escribe en el cuadro de búsqueda (`🔍`) para filtrar los archivos en tiempo real.
  - Puedes escribir términos como `lema-de-gronwall`, `jose-juan-urrutia-milan` o el nombre de una carpeta (ej. `concepts`).
  - Al escribir, el buscador muestra únicamente los archivos que coincidan y abre/cierra automáticamente las carpetas pertinentes.
  - Utiliza el botón **`✕`** para limpiar la búsqueda instantáneamente.
- **Botones de Control Global**:
  - **`➕ Abrir todas`**: Expande simultáneamente todas las carpetas del repositorio para ver la estructura completa de un vistazo.
  - **`➖ Cerrar todas`**: Colapsa todas las carpetas, dejando visible únicamente los encabezados principales.

---

### Visor Markdown en Vivo con Soporte YAML y Wiki-links

Al hacer clic en cualquier documento (`📄 nombre-del-archivo.md`) dentro del explorador, se abre el visor integrado de Moodle (`/blocks/gitmetrics/view_file.php`):

1. **Lectura en Memoria RAM (Cero Almacenamiento)**: El contenido es descargado directamente desde la API del servidor Git (GitHub o GitLab) en memoria en el momento en que lo solicitas. **No se almacena ni duplica ningún archivo en el servidor Moodle**, garantizando que siempre leas la versión más reciente y preservando el espacio en disco.
2. **Ficha Estructurada de Metadatos YAML (Frontmatter)**:
   - Si el archivo comienza con un bloque de cabecera YAML (`---`), el visor lo extrae y lo presenta en una elegante tarjeta visual de metadatos justo encima del documento.
   - Muestra de forma limpia el **Título** (`title`), **Descripción** (`description`), **Tipos de Entidad** (`type`), **Etiquetas** (`tags` con formato pill de colores), **Claims** y **Recurso Asociado** (`resource`).
3. **Hipervínculos Internos al estilo Obsidian (`[[wiki-links]]`)**:
   - El visor reconoce automáticamente cualquier enlace interno en formato Obsidian/Wiki-link (ej. `[[okf/entities/jose-juan-urrutia-milan|José Juan Urrutia Milán]]` o `[[okf/concepts/lema-de-gronwall]]`).
   - Los transforma al vuelo en enlaces clicables propios de Moodle que te llevan directamente al documento referenciado sin salir del visor ni perder el contexto de navegación.
4. **Enlace al Repositorio Remoto (`↗`)**:
   - En la parte superior de la ficha y en cada fila del explorador, dispones del botón **`↗ Ver en GitLab/GitHub`**, que abre una pestaña hacia la fuente original en el servidor Git externo.

---

### Secciones de Métricas Cuantitativas (Secciones 1 a 4)

Debajo del explorador de documentos, la asignatura muestra el análisis estadístico y de calidad estructural en 4 grandes bloques colapsables:

1. **`Volumen y Tamaño de la Base de Conocimiento`**: Muestra tarjetas con el recuento total de archivos Markdown (`.md`), total de ficheros del repo, profundidad máxima de carpetas, tamaño medio y palabras totales/medias. Además, evalúa con insignias verdes/rojas la presencia de ficheros esenciales del marco OKF (`README.md`, `INDEX.md`, `LICENSE`, `SUMMARY.md`, `CONTRIBUTING.md`).
2. **`Red de Enlaces e Interconectividad Markdown`**: Analiza el grafo de conocimiento. Muestra el número total de nodos, enlaces internos, conexiones medias por documento, densidad de enlaces, porcentaje de conectividad e **índice de notas huérfanas** (documentos aislados sin enlaces entrantes o salientes).
3. **`Taxonomía, Metadatos y Etiquetas YAML`**: Cuenta el porcentaje de documentos con frontmatter YAML válido, genera una nube de etiquetas (`tags`) interactiva con las frecuencias de cada categoría y presenta la tabla de campos utilizados.
4. **`Calidad Markdown y Elementos Estructurales`**: Mide la riqueza del formato mediante el promedio y conteo total de encabezados (`H1-H6`), bloques de código, fórmulas matemáticas LaTeX (`$$` y `$`), tablas, imágenes, listas y citas (`blockquote`).

---

### Uso como Pestaña Superior en Cualquier Asignatura

Además del curso central, el plugin se integra de forma transparente en todas las asignaturas de tu Moodle:
1. Accede a cualquier curso de Moodle como profesor o administrador.
2. En la barra de navegación secundaria superior (*Curso | Configuración | Participantes | Calificaciones | ...*), verás la pestaña **`Métricas de Base de Conocimiento Git`**.
3. Al pulsarla, accederás a la vista a pantalla completa (`/blocks/gitmetrics/view.php`) con las métricas del repositorio configurado o asociado a dicha asignatura.

---

### Uso como Bloque en el Menú Lateral

Si prefieres tener un resumen compacto en el cajón lateral:
1. Dentro de una asignatura, haz clic en **Activar edición** (arriba a la derecha).
2. Abre el cajón derecho de bloques o haz clic en **Añadir un bloque**.
3. Selecciona **Métricas de Base de Conocimiento Git** (`Git Knowledge Base Metrics`).
4. Pulsa en el icono de engranaje del bloque -> **Configurar bloque** para asociarle una URL concreta de GitHub o GitLab.

---

## 5. Configuración de Proveedores (GitHub vs GitLab)

El plugin soporta de forma nativa dos grandes proveedores Git mediante autenticación con tokens:

| Proveedor | Cuándo Elegirlo | URL del Repositorio | Token Necesario |
| :--- | :--- | :--- | :--- |
| **GitHub** | Para proyectos y repositorios alojados en `github.com`. | `https://github.com/owner/repo` | GitHub Personal Access Token (PAT) clásico con scope `repo` o `public_repo`. Configurable en *Administración del sitio > Plugins > Bloques > Git Knowledge Base Metrics*. |
| **GitLab (OSL / Local / Cloud)** | Para el servidor de la Oficina de Software Libre (OSL) de tu universidad, servidores locales de laboratorio o `gitlab.com`. | `https://gitlab.osl.ugr.es/owner/repo`<br>`http://localhost:8929/owner/repo` | GitLab Access Token (`PRIVATE-TOKEN`) con scope `read_api`. |

**Ventajas de usar GitLab institucional (OSL / Local):**
- **Cero límites de peticiones (Rate Limiting)**: La API local o de la universidad permite analizar miles de archivos de forma inmediata sin topes de peticiones por hora.
- **Soberanía Académica**: Los datos de los estudiantes y apuntes no salen de los servidores universitarios.
- **Tolerancia a SSL Autofirmado**: El cliente incluye soporte en el motor HTTP de Moodle (`ignoresecurity => true`) para conectarse sin errores a servidores locales de desarrollo en HTTPS o HTTP.

---

## 6. Credenciales del Entorno

| Servicio | URL Local | Usuario | Contraseña |
| :--- | :--- | :--- | :--- |
| **Moodle 4.2+** | `http://localhost:8000` | `admin` | `adminpass123` |
| **Element Web (Matrix Client)** | `http://localhost:8081` | `admin` | `adminpass123` |
| **MariaDB (Base de datos)** | Interno en contenedor (`localhost:3306`) | `bn_moodle` | `moodle_db_pass` |

---

## 📚 Documentación Técnica Detallada

Para conocer la arquitectura orientada a objetos (`git_provider_interface`, `metrics_cache`, `markdown_parser`), las consultas SQL del esquema y referencias adicionales, consulta la documentación en **[`gitmetrics/README.md`](./gitmetrics/README.md)**.
