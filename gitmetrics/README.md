# block_gitmetrics — Plugin de Moodle para Evaluación de Bases de Conocimiento Git y OKF

`block_gitmetrics` es un plugin oficial de bloque para Moodle 4.2+ que conecta cualquier asignatura o el entorno escolar completo con repositorios externos de **GitHub** o **GitLab** organizados bajo el **Open Knowledge Framework (OKF)**.

Proporciona un cuadro de mando estadístico de la base de conocimiento y un explorador de documentos interactivo con visor en memoria RAM (sin almacenamiento local en disco) que transforma apuntes Markdown y fichas YAML en recursos educativos navegables dentro de Moodle.

---

## 🏗️ Estructura del Plugin y Explicación de Ficheros

Cada fichero del plugin tiene una función específica orientada al rendimiento, modularidad y compatibilidad con las APIs de Moodle:

```text
gitmetrics/
├── block_gitmetrics.php          Clase principal del bloque Moodle (`block_base`). Gestiona la instancia, la lectura del proveedor de configuración, invocación del caché/calculador y el renderizado final en bloque o pantalla.
├── version.php                   Declaración de versión (`$plugin->version`), requisitos de Moodle (`requires = 2022041900`) y madurez (`MATURITY_STABLE`).
├── settings.php                  Ajustes globales del administrador (Administración > Plugins > Bloques > Git Knowledge Base Metrics): proveedor por defecto, tokens API (GitHub/GitLab), URL servidor GitLab, TTL del caché y rama por defecto.
├── edit_form.php                 Formulario de configuración por instancia (`block_edit_form`). Permite al profesor sobrescribir en una asignatura concreta la URL del repo, proveedor y rama, o forzar la actualización del caché.
├── renderer.php                  Motor de visualización Moodle (`plugin_renderer_base`). Genera el HTML/CSS para las 4 secciones cuantitativas (Volumen, Red de Enlaces, Taxonomía, Calidad Markdown) y tarjetas estadísticas.
├── view.php                      Página central de informe a pantalla completa (`/blocks/gitmetrics/view.php`). Accesible vía pestaña superior o enlace principal, muestra los acordeones de métricas aprovechando el 100% del ancho del curso.
├── view_file.php                 Visor en vivo de ficheros Markdown (`/blocks/gitmetrics/view_file.php`). Descarga en memoria RAM el contenido raw vía API, parsea frontmatter YAML mostrando una ficha estructurada de metadatos, resuelve enlaces `[[wiki-links]]` hacia URLs internas de Moodle y renderiza el cuerpo con `format_text()`.
├── lib.php                       Biblioteca auxiliar del plugin. Implementa el gancho `block_gitmetrics_extend_navigation_course` que añade la pestaña de métricas en la barra superior de las asignaturas.
├── classes/                      Lógica de negocio orientada a objetos (Autocargable por Moodle):
│   ├── git_provider_interface.php  Interfaz `git_provider_interface` que estandariza los métodos (`get_repo_info`, `get_tree`, `get_file_content`) para cualquier proveedor Git.
│   ├── github_client.php           Implementación de cliente HTTP para la API REST v3 de GitHub utilizando `curl` nativo de Moodle.
│   ├── gitlab_client.php           Implementación de cliente HTTP para la API REST v4 de GitLab con paginación automática (100 ítems/página) y soporte de SSL autofirmado (`ignoresecurity`).
│   ├── markdown_parser.php         Analizador sintáctico que extrae frontmatter YAML, detecta enlaces `[[wiki-links]]`, calcula densidades de grafo, identifica notas huérfanas y mide elementos estructurales (LaTeX, tablas, headers, code blocks).
│   ├── metrics_calculator.php      Orquestador que descarga el árbol completo del repositorio y ejecuta los análisis cuantitativos divididos en las 4 categorías clave.
│   └── metrics_cache.php           Gestor de persistencia temporal en base de datos (`mdl_block_gitmetrics_cache`) que almacena los resultados serializados para evitar llamadas repetidas a las APIs externas según el TTL configurado.
├── cli/                          Herramientas de automatización por línea de comandos:
│   └── setup_course.php            Script CLI que crea/actualiza la asignatura dedicada "Panel de Métricas y BdC" (ID: 4), matricula al usuario `admin` como docente y puebla las 5 secciones (`Acceso a Documentos` + 4 categorías de métricas).
├── db/                           Esquemas y permisos de Moodle:
│   ├── access.php                  Definición de capacidades (`block/gitmetrics:addinstance`, `block/gitmetrics:myaddinstance`, `block/gitmetrics:viewmetrics`).
│   ├── install.xml                 Esquema XMLDB que define la tabla `mdl_block_gitmetrics_cache` para persistencia de cálculos.
│   └── upgrade.php                 Controlador de migraciones de base de datos entre versiones del plugin.
└── lang/                         Paquetes de internacionalización (i18n):
    ├── en/block_gitmetrics.php     Cadenas en idioma inglés (idioma por defecto del core).
    └── es/block_gitmetrics.php     Cadenas traducidas al español.
```

---

## 🚀 Instalación y Puesta en Marcha

Para una instalación limpia en tu entorno de desarrollo local con Docker, ejecuta el guion automatizado desde la raíz del proyecto en WSL:

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas
./instalar.sh
```

### Proceso Interno de Instalación (`instalar.sh`)
1. **Inicio de Contenedores**: Llama a `docker compose up -d` en `moodle-matrix-dev/` para arrancar Moodle, MariaDB, Synapse y Element.
2. **Sondeo de Disponibilidad**: Realiza comprobaciones periódicas contra PHP (`docker exec moodle-app php -r "echo 'OK';"`) hasta que la base de datos y el servidor web están inicializados.
3. **Inyección del Plugin**: Copia el directorio `gitmetrics/` en la ruta `/bitnami/moodle/blocks/gitmetrics/` del contenedor principal.
4. **Permisos Daemon**: Asigna la propiedad recursiva a `daemon:daemon` (usuario de Apache/PHP en Bitnami) para que Moodle pueda procesar el código sin errores de lectura.
5. **Registro SQL (`upgrade.php`)**: Ejecuta el actualizador de Moodle en modo no interactivo para crear la tabla de caché (`mdl_block_gitmetrics_cache`) y registrar el bloque en el sistema.
6. **Creación del Curso Dedicado (`setup_course.php`)**: Ejecuta el script CLI que construye el curso centralizado, inyecta el árbol de carpetas con buscador instantáneo en el Tema 0 y calcula las métricas para los Temas 1-4.

---

## 🛠️ Guía Paso a Paso de Uso en Moodle

### 1. Acceder al Panel General
Al finalizar `./instalar.sh`, accede a Moodle desde tu navegador:
- **URL**: `http://localhost:8000`
- **Usuario**: `admin`
- **Contraseña**: `adminpass123`

En la pantalla principal (`Mis cursos`) verás la tarjeta del curso **`Panel de Métricas y BdC`**. Haz clic para entrar.

---

### 2. Explorar y Buscar Documentos Markdown (Sección 0)
En el primer apartado del curso se carga dinámicamente la sección **`📂 Acceso a Documentos de la Base de Conocimiento`**:

- **Navegación por Carpetas Colapsables (`<details>`)**: Las rutas del repositorio git remoto (por ejemplo `okf/concepts`, `okf/entities`) se agrupan en acordeones colapsables. Haz clic sobre el nombre de la carpeta (o la flecha `▼`) para desplegar u ocultar los archivos que contiene.
- **Filtrado en Tiempo Real mediante la Barra de Búsqueda**:
  - En el campo **`🔍 Buscar documento por nombre, ruta o carpeta...`**, escribe cualquier término (ej. `lema-de-gronwall`, `ecuacion`, `concepts`).
  - El buscador oculta al instante las filas que no coinciden con tu consulta y abre automáticamente las carpetas donde haya aciertos.
  - El contador azul inferior te indicará en todo momento: `✅ Encontrados X archivos coincidentes` o `❌ No se encontraron archivos coincidentes con '...'`.
  - Haz clic en el botón **`✕`** dentro de la barra para limpiar tu búsqueda y restaurar la vista original.
- **Botones Globales de Expansión/Compresión**:
  - **`➕ Abrir todas`**: Despliega todas las carpetas colapsables de golpe para visualizar el listado general del repositorio en la misma pantalla.
  - **`➖ Cerrar todas`**: Colapsa todas las carpetas para dejar visible únicamente los títulos principales de los directorios.

---

### 3. Visualizar Ficheros con Metadatos YAML y Wiki-links
Haz clic en el enlace de cualquier documento (icono `📄`) o en el botón externo `↗`:

- **Apertura Interna (`view_file.php`)**: Al hacer clic sobre el nombre del fichero, se abre la vista enriquecida en Moodle.
  - **Ficha YAML (Frontmatter)**: Si el fichero tiene metadatos en su cabecera (entre `---`), verás una tarjeta visual de color azulado y púrpura con el **Título**, **Descripción**, **Recursos** y pastillas estilizadas con las **Etiquetas (`tags`)**.
  - **Soporte de `[[wiki-links]]`**: Los enlaces en corchetes dobles de estilo Obsidian se convierten automáticamente en links internos que apuntan al documento de destino dentro de la propia plataforma Moodle.
  - **Cero Disco**: El archivo no se descarga como adjunto ni se guarda en Moodle; se renderiza al vuelo desde la memoria RAM.
- **Apertura Externa (`↗`)**: Cada fila dispone del botón `↗` para abrir el fichero directamente en la interfaz de GitLab o GitHub en una pestaña nueva del navegador.

---

### 4. Analizar el Cuadro de Mando Cuantitativo (Secciones 1 a 4)
Justo debajo del explorador de documentos verás los 4 grandes bloques cuantitativos calculados sobre el repositorio:
1. **Volumen y Tamaño**: Estadísticas generales (total `.md`, profundidad de árbol, promedio de palabras) y control de ficheros estructurales de OKF (`README.md`, `SUMMARY.md`, etc.).
2. **Red de Enlaces**: Análisis del grafo con recuento de conexiones, índice de densidad, porcentaje de interconectividad y **tasa de notas huérfanas** (documentos aislados).
3. **Taxonomía YAML**: Nube de palabras de etiquetas (`tags`) con su frecuencia e índice de adopción de frontmatter en los apuntes del repositorio.
4. **Calidad y Estructura**: Frecuencia media y total por archivo de elementos avanzados: fórmulas matemáticas LaTeX (`$$`), tablas Markdown, bloques de código, encabezados (`H1-H6`) y citas.

---

### 5. Añadir el Bloque o Pestaña en Otras Asignaturas
El plugin es flexible y se puede asociar a cualquier otra asignatura o curso de tu plataforma:
- **Opción Pestaña Superior**: Al entrar en cualquier curso, haz clic en la pestaña superior **`Métricas de Base de Conocimiento Git`** en la barra de navegación del docente.
- **Opción Bloque Lateral**: En cualquier curso, activa la edición -> **Añadir un bloque** -> selecciona **Métricas de Base de Conocimiento Git** (`Git Knowledge Base Metrics`) y entra en **Configurar bloque** para asociarle la URL del repositorio Git deseado.

---

## ⚙️ Arquitectura Técnica y Caché

### Interfaz Única de Proveedores (`git_provider_interface`)
El sistema está diseñado de forma modular para que los clientes de GitHub y GitLab compartan la misma interfaz:
```php
interface git_provider_interface {
    public function get_repo_info(string $owner, string $repo): array;
    public function get_tree(string $owner, string $repo, string $branch = 'main'): array;
    public function get_file_content(string $owner, string $repo, string $filepath, string $branch = 'main'): string;
}
```

### Sistema de Caché en Base de Datos (`metrics_cache`)
Para no sobrecargar los servidores Git externos ni alcanzar los límites de peticiones por hora (Rate Limit):
- Las métricas calculadas y la estructura se guardan en formato JSON dentro de la tabla de Moodle `mdl_block_gitmetrics_cache`.
- El Tiempo de Vida (TTL) predeterminado es de **1 hora** (configurable desde Ajustes Globales).
- El docente puede solicitar un cálculo inmediato marcando la casilla **`Forzar actualización de métricas`** (`force_refresh`) en la configuración del bloque.
