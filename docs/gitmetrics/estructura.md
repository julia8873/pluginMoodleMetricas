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
