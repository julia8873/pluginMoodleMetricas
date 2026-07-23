# block_gitmetrics — Plugin de Moodle para Evaluación de Bases de Conocimiento Git y OKF

`block_gitmetrics` es un plugin oficial de bloque para Moodle 4.2+ que conecta cualquier asignatura con repositorios externos de **GitHub** o **GitLab** organizados bajo el **Open Knowledge Framework (OKF)**.

Proporciona un cuadro de mando cuantitativo y estadístico que analiza el volumen, grafo de enlaces, taxonomía YAML y calidad estructural de los apuntes y documentación Markdown.

---

## Estructura del Plugin

```text
gitmetrics/
├-- block_gitmetrics.php          Clase principal del bloque Moodle (`block_base`).
├-- version.php                   Declaración de versión y compatibilidad (`requires = 2022041900`).
├-- settings.php                  Ajustes globales de administración: proveedor, tokens API, URL GitLab y TTL de caché.
├-- edit_form.php                 Formulario de configuración por instancia de bloque en una asignatura.
├-- renderer.php                  Renderizador Moodle (`plugin_renderer_base`). Genera el HTML y CSS de las métricas.
├-- view.php                      Página central de informe a pantalla completa (`/blocks/gitmetrics/view.php`).
├-- view_file.php                 Visor integrado de documentos.
├-- lib.php                       Gancho de navegación (`extend_navigation_course`) para añadir la pestaña superior en cursos.
├-- classes/
│   ├-- git_provider_interface.php  Interfaz común para proveedores Git (`get_repo_info`, `get_tree`, `get_file_content`).
│   ├-- github_client.php           Cliente HTTP para la API REST v3 de GitHub.
│   ├-- gitlab_client.php           Cliente HTTP para la API REST v4 de GitLab (con paginación y soporte SSL autofirmado).
│   ├-- markdown_parser.php         Analizador sintáctico de frontmatter YAML, enlaces y elementos estructurales.
│   ├-- metrics_calculator.php      Orquestador que descarga el árbol del repositorio y calcula las métricas cuantitativas.
│   ├-- metrics_cache.php           Gestor de persistencia temporal en base de datos (`mdl_block_gitmetrics_cache`) con TTL.
│   ├-- matrix_helper.php           Integración con Matrix/Synapse: crea salas de chat por asignatura automáticamente.
│   ├-- obsidian_exporter.php       [OPCIONAL] Exporta todos los .md del repo a un vault local de Obsidian. Eliminar para desactivar.
│   └-- task/
│       └-- sync_obsidian.php       [OPCIONAL] Tarea programada Moodle para sincronización automática con Obsidian.
├-- cli/
│   ├-- setup_course.php            Script CLI para inicializar y configurar la asignatura dedicada "Panel de Métricas y BdC".
│   ├-- setup_git.php               Script CLI para configurar los parámetros de conexión Git (token, URL, proveedor).
│   ├-- setup_matrix.php            Script CLI para automatizar la configuración del subsistema Matrix, token, seguridad cURL y sala.
│   ├-- setup_obsidian.php          [OPCIONAL] CLI para la primera configuración y sincronización con Obsidian.
│   └-- export_obsidian.php         [OPCIONAL] CLI para sincronizar manualmente el repositorio con el vault de Obsidian.
├-- db/
│   ├-- access.php                  Capacidades y permisos del bloque.
│   ├-- install.xml                 Esquema XMLDB de la tabla de caché.
│   ├-- tasks.php                   Registro de tareas programadas (sync_obsidian).
│   └-- upgrade.php                 Controlador de migraciones de base de datos.
└-- lang/
    ├-- en/block_gitmetrics.php     Cadenas de texto en inglés.
    └-- es/block_gitmetrics.php     Cadenas de texto en español.
```
