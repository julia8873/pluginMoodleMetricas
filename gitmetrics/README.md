# block_gitmetrics — Plugin de Moodle para Evaluación de Bases de Conocimiento Git y OKF

`block_gitmetrics` es un plugin oficial de bloque para Moodle 4.2+ que conecta cualquier asignatura con repositorios externos de **GitHub** o **GitLab** organizados bajo el **Open Knowledge Framework (OKF)**.

Proporciona un cuadro de mando cuantitativo y estadístico que analiza el volumen, grafo de enlaces, taxonomía YAML y calidad estructural de los apuntes y documentación Markdown.

---

## Estructura del Plugin

```text
gitmetrics/
├── block_gitmetrics.php          Clase principal del bloque Moodle (`block_base`).
├── version.php                   Declaración de versión y compatibilidad (`requires = 2022041900`).
├── settings.php                  Ajustes globales de administración: proveedor, tokens API, URL GitLab y TTL de caché.
├── edit_form.php                 Formulario de configuración por instancia de bloque en una asignatura.
├── renderer.php                  Renderizador Moodle (`plugin_renderer_base`). Genera el HTML y CSS de las métricas.
├── view.php                      Página central de informe a pantalla completa (`/blocks/gitmetrics/view.php`).
├── view_file.php                 Visor integrado de documentos.
├── lib.php                       Gancho de navegación (`extend_navigation_course`) para añadir la pestaña superior en cursos.
├── classes/
│   ├── git_provider_interface.php  Interfaz común para proveedores Git (`get_repo_info`, `get_tree`, `get_file_content`).
│   ├── github_client.php           Cliente HTTP para la API REST v3 de GitHub.
│   ├── gitlab_client.php           Cliente HTTP para la API REST v4 de GitLab (con paginación y soporte SSL autofirmado).
│   ├── markdown_parser.php         Analizador sintáctico de frontmatter YAML, enlaces y elementos estructurales.
│   ├── metrics_calculator.php      Orquestador que descarga el árbol del repositorio y calcula las métricas cuantitativas.
│   ├── metrics_cache.php           Gestor de persistencia temporal en base de datos (`mdl_block_gitmetrics_cache`) con TTL.
│   └── obsidian_exporter.php       [OPCIONAL] Exporta todos los .md del repo a un vault local de Obsidian. Eliminar para desactivar.
├── cli/
│   ├── setup_course.php            Script CLI para inicializar y poblar la asignatura dedicada "Panel de Métricas y BdC".
│   └── export_obsidian.php         [OPCIONAL] CLI para sincronizar el repositorio con el vault de Obsidian. Eliminar para desactivar.
├── db/
│   ├── access.php                  Capacidades y permisos del bloque.
│   ├── install.xml                 Esquema XMLDB de la tabla de caché.
│   └── upgrade.php                 Controlador de migraciones de base de datos.
└── lang/
    ├── en/block_gitmetrics.php     Cadenas de texto en inglés.
    └── es/block_gitmetrics.php     Cadenas de texto en español.
```

---

## Instalación y Puesta en Marcha

Para una instalación limpia mediante un solo comando desde la raíz del proyecto en WSL:

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas
./instalar.sh
```

El script `instalar.sh` se encarga de levantar Docker, esperar al servidor Moodle, copiar el directorio `gitmetrics/`, ajustar los permisos, ejecutar el registro en base de datos (`upgrade.php`) y poblar la asignatura inicial (`setup_course.php`).

---

## Secciones de Métricas Cuantitativas

El plugin calcula y estructura el análisis estadístico del repositorio en 4 categorías cuantitativas:

1. **Volumen y Tamaño**: Estadísticas generales (total de archivos `.md`, profundidad de árbol, promedio de palabras por documento) y verificación de existencia de ficheros estructurales OKF (`README.md`, `SUMMARY.md`, `LICENSE`, `CONTRIBUTING.md`).
2. **Red de Enlaces**: Análisis de interconectividad con recuento de conexiones internas, densidad del grafo, porcentaje de documentos interconectados e **índice de notas huérfanas** (documentos aislados sin enlaces).
3. **Taxonomía YAML**: Nube de palabras de etiquetas (`tags`) con su frecuencia de uso y porcentaje de adopción de frontmatter en los documentos.
4. **Calidad y Estructura**: Frecuencia media y total por archivo de elementos sintácticos avanzados: fórmulas matemáticas LaTeX (`$$` y `$`), tablas Markdown, bloques de código, encabezados (`H1-H6`) y citas.

---

## Guía Rápida de Uso en Moodle

### 1. Acceder a la Asignatura Dedicada
Al finalizar la instalación, entra a Moodle:
- **URL**: `http://localhost:8000`
- **Usuario**: `admin`
- **Contraseña**: `adminpass123`

En **Mis cursos** haz clic en **`Panel de Métricas y BdC`** para visualizar de inmediato el panel estadístico general.

### 2. Uso como Pestaña Superior en Otras Asignaturas
Dentro de cualquier asignatura de tu Moodle verás en la barra superior del curso la pestaña **`Métricas de Base de Conocimiento Git`**. Al pulsarla accederás al informe cuantitativo completo en pantalla completa.

### 3. Uso como Bloque en el Menú Lateral
1. Activa la edición en cualquier curso (`Activar edición`).
2. En el cajón derecho o menú de bloques haz clic en **Añadir un bloque** -> **Métricas de Base de Conocimiento Git**.
3. Pulsa el icono de engranaje -> **Configurar bloque** y especifica la URL de GitHub o GitLab del repositorio a analizar.

---

## Integración con Obsidian (Módulo Opcional)

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

## Arquitectura Técnica y Caché

### Interfaz Única de Proveedores (`git_provider_interface`)
El sistema abstrae la obtención de datos mediante una interfaz estandarizada implementada por `github_client` y `gitlab_client`:
```php
interface git_provider_interface {
    public function get_repo_info(string $owner, string $repo): array;
    public function get_tree(string $owner, string $repo, string $branch = 'main'): array;
    public function get_file_content(string $owner, string $repo, string $filepath, string $branch = 'main'): string;
}
```

### Sistema de Caché en Base de Datos (`metrics_cache`)
Para optimizar el tiempo de respuesta y evitar alcanzar límites por IP en APIs externas:
- Las métricas calculadas se serializan en la tabla `mdl_block_gitmetrics_cache`.
- El Tiempo de Vida (TTL) por defecto es de **1 hora** (modificable por el administrador del sitio).
- Desde la configuración del bloque, un docente puede marcar **`Forzar actualización de métricas`** para invalidar la caché e interrogar directamente al servidor remoto en ese instante.
