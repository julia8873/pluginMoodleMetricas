# block_gitmetrics — Plugin de Moodle para Evaluación de Bases de Conocimiento Git y OKF

`block_gitmetrics` es un plugin oficial de bloque para Moodle 4.2+ que conecta cualquier asignatura con repositorios externos de **GitHub** o **GitLab** organizados bajo el **Open Knowledge Framework (OKF)**.

Proporciona un cuadro de mando cuantitativo y estadístico que analiza el volumen, grafo de enlaces, taxonomía YAML y calidad estructural de los apuntes y documentación Markdown.

---

## Estructura del Plugin

```text
gitmetrics/
├-- block_gitmetrics.php          Clase principal del bloque Moodle.
├-- version.php                   Declaración de versión y compatibilidad.
├-- settings.php                  Ajustes globales de administración: proveedor, tokens API, URL GitLab y TTL de caché.
├-- edit_form.php                 Formulario de configuración por instancia de bloque en una asignatura.
├-- renderer.php                  Renderizador Moodle. Genera el HTML y CSS de las métricas.
├-- view.php                      Página central de informe a pantalla completa.
├-- view_file.php                 Visor integrado de documentos.
├-- lib.php                       Gancho de navegación para añadir la pestaña superior en cursos.
├-- classes/
│   ├-- git_provider_interface.php  Interfaz común para proveedores Git.
│   ├-- github_client.php           Cliente HTTP para la API REST v3 de GitHub.
│   ├-- gitlab_client.php           Cliente HTTP para la API REST v4 de GitLab.
│   ├-- markdown_parser.php         Analizador sintáctico de frontmatter YAML, enlaces y elementos estructurales.
│   ├-- metrics_calculator.php      Orquestador que descarga el árbol del repositorio y calcula las métricas cuantitativas.
│   ├-- metrics_cache.php           Gestor de persistencia temporal en base de datos con TTL.
│   ├-- matrix_helper.php           Integración con Matrix/Synapse: crea salas de chat por asignatura automáticamente.
│   ├-- obsidian_exporter.php       Exporta todos los .md del repo a un vault local de Obsidian.
│   └-- task/
│       └-- sync_obsidian.php       Tarea programada Moodle para sincronización automática con Obsidian.
├-- cli/
│   ├-- setup_course.php            Script CLI para inicializar y configurar la asignatura dedicada "Panel de Métricas y BdC".
│   ├-- setup_git.php               Script CLI para configurar los parámetros de conexión Git (token, URL, proveedor).
│   ├-- setup_matrix.php            Script CLI para automatizar la configuración del subsistema Matrix, token, seguridad cURL y sala.
│   ├-- setup_obsidian.php          Script CLI para la primera configuración y sincronización con Obsidian.
│   └-- export_obsidian.php         Script CLI para sincronizar manualmente el repositorio con el vault de Obsidian.
├-- db/
│   ├-- access.php                  Capacidades y permisos del bloque.
│   ├-- install.xml                 Esquema XMLDB de la tabla de caché.
│   ├-- tasks.php                   Registro de tareas programadas (sync_obsidian).
│   └-- upgrade.php                 Controlador de migraciones de base de datos.
└-- lang/
    ├-- en/block_gitmetrics.php     Cadenas de texto en inglés.
    └-- es/block_gitmetrics.php     Cadenas de texto en español.
```


---

<a id="uso"></a>
## Guía de Uso: Secciones de Métricas

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

---

<a id="obsidian"></a>
## Integración con Obsidian

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