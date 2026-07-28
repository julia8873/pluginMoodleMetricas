# Estructura del Plugin

La estructura principal del plugin `gitmetrics` es la siguiente:

- `block_gitmetrics.php`: Clase principal del bloque Moodle (`block_base`).
- `version.php`: Declaración de versión y compatibilidad (`requires = 2022041900`).
- `settings.php`: Ajustes globales de administración: proveedor, tokens API, URL GitLab y TTL de caché.
- `edit_form.php`: Formulario de configuración por instancia de bloque en una asignatura.
- `renderer.php`: Renderizador Moodle (`plugin_renderer_base`). Genera el HTML y CSS de las métricas.
- `view.php`: Página central de informe a pantalla completa (`/blocks/gitmetrics/view.php`).
- `view_file.php`: Visor integrado de documentos.
- `lib.php`: Gancho de navegación (`extend_navigation_course`) para añadir la pestaña superior en cursos.

## Directorios

- `classes/`: Contiene las interfaces y clientes para los proveedores Git (GitHub, GitLab), el analizador Markdown y el calculador de métricas.
- `cli/`: Scripts de línea de comandos para la configuración inicial y sincronización.
- `db/`: Esquemas de base de datos, tareas programadas y capacidades.
- `lang/`: Archivos de idioma (Inglés y Español).

## Esquema de Base de Datos (`db/`)

Todas las tablas se definen en `db/install.xml` y se migran mediante `db/upgrade.php`.
La versión actual del plugin es `2026072800`.

### `block_gitmetrics_cache` — Caché de métricas (v inicial)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| `id` | INT(10) | NO | PK autoincremental |
| `blockinstanceid` | INT(10) | NO | `mdl_block_instances.id` |
| `repo_url` | CHAR(500) | NO | URL completa del repo analizado |
| `repo_url_hash` | CHAR(32) | NO | MD5 de `repo_url` para búsqueda rápida |
| `metrics_json` | TEXT | NO | JSON con todas las métricas calculadas |
| `timecreated` | INT(10) | NO | Unix timestamp de creación |
| `timemodified` | INT(10) | NO | Unix timestamp de última actualización |

Índice: `(blockinstanceid, repo_url_hash)` no único.

### `block_gitmetrics_progress_cache` — Caché de progreso del bot (v2026072700)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| `id` | INT(10) | NO | PK autoincremental |
| `blockinstanceid` | INT(10) | NO | `mdl_block_instances.id` |
| `course_id` | INT(10) | NO | `mdl_course.id` |
| `progress_json` | TEXT | NO | JSON de progreso devuelto por el endpoint `/progreso` del bot |
| `timecreated` | INT(10) | NO | Unix timestamp de creación |
| `timemodified` | INT(10) | NO | Unix timestamp de última actualización |

Índice: `(blockinstanceid, course_id)` no único.

### `block_gitmetrics_course_repo` — Repo de curso (v2026072800)

Almacena el repositorio GitHub/GitLab creado a partir de la plantilla BdC para cada curso.
Hay **un único registro por curso** (índice único en `course_id`).

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| `id` | INT(10) | NO | PK autoincremental |
| `course_id` | INT(10) | NO | `mdl_course.id` |
| `repo_url` | CHAR(500) | NO | URL HTML del repo creado (`https://github.com/...`) |
| `provider` | CHAR(20) | NO | Proveedor Git: `github` \| `gitlab` |
| `status` | CHAR(20) | NO | Estado: `pendiente` \| `creado` \| `error` (default `pendiente`) |
| `error_msg` | TEXT | SÍ | Mensaje de error si `status = error`; NULL si no hay error |
| `timecreated` | INT(10) | NO | Unix timestamp de creación |

Índice: `(course_id)` **único**.

### `block_gitmetrics_student_fork` — Fork personal del alumno (v2026072800)

Almacena el fork personal creado para cada alumno dentro de un curso.
Hay **un único fork por combinación `course_id + userid`** (índice único compuesto).

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| `id` | INT(10) | NO | PK autoincremental |
| `course_id` | INT(10) | NO | `mdl_course.id` |
| `userid` | INT(10) | NO | `mdl_user.id` |
| `id_pseudo` | CHAR(36) | NO | UUID pseudónimo del alumno (mismo `id_pseudo` que genera `db.py` del bot) |
| `fork_url` | CHAR(500) | SÍ | URL HTML del fork (`https://github.com/...`); NULL mientras `status = pendiente` |
| `status` | CHAR(20) | NO | Estado: `pendiente` \| `creado` \| `error` (default `pendiente`) |
| `error_msg` | TEXT | SÍ | Mensaje de error si `status = error`; NULL si no hay error |
| `timecreated` | INT(10) | NO | Unix timestamp de creación |

Índice: `(course_id, userid)` **único**.

> [!NOTE]
> El campo `status` con tres estados (`pendiente` / `creado` / `error`) es compartido por ambas tablas de aprovisionamiento. El Paso 10 del plan (`retry_provisioning.php`) consulta todos los registros con `status = 'error'` o `status = 'pendiente'` para reintentarlos vía scheduled task de Moodle.

