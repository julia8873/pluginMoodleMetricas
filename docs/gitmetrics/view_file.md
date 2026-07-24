Crear archivo en: `docs/gitmetrics/view_file.md`

# Archivo `view_file`

Ubicación: `view_file.php`

--8<-- "gitmetrics/view_file.php:file_desc"

## Diagrama de Flujo Principal

```mermaid
graph TD
    A["1. Clic en enlace de archivo desde UI"] --> B["2. Validar parámetros y login"]
    B --> C{"¿Faltan parámetros URL?"}
    C -->|"Sí"| D["3. Mostrar pantalla de error"]
    C -->|"No"| E["4. Cargar credenciales del proveedor Git"]
    E --> F["5. Descargar fichero markdown en memoria RAM"]
    F --> G["6. Parsear Frontmatter YAML"]
    G --> H["7. Reemplazar [[WikiLinks"]] por URLs Moodle]
    H --> I["8. Renderizar cuerpo Markdown a HTML"]
    I --> J["9. Construir y pintar Ficha de Metadatos"]
    J --> K["10. Pintar documento integrado en UI de Moodle"]
```

### Detalle de los Pasos del Flujo

1. **[PASO 1] Disparador:** El usuario pulsa sobre un archivo `.md` en la tabla de métricas (vista lateral o completa).
2. **[PASO 2] Validación Inicial:** Requerimos que el entorno de Moodle esté autenticado (`require_login`), verificando la capacidad (`block/gitmetrics:viewmetrics`) sobre el contexto.
3. **[PASO 3] Control de Errores:** Si la variable GET `path` o `repo_url` están vacías, se aborta y se pinta un *dump* de error en pantalla.
4. **[PASO 4] Configuración del Cliente:** Basándose en si la URL contiene "github.com", se instancia automáticamente `github_client` o `gitlab_client` utilizando los tokens correspondientes del panel de administración.
5. **[PASO 5] Extracción Remota:** Llama al API del proveedor con `get_file_content` para traer todo el documento a memoria. Nunca se guardan copias en el disco duro del servidor de Moodle.
6. **[PASO 6] YAML Parsing:** Se ejecuta `gmv_parse_frontmatter` para extraer propiedades clave y separarlas del cuerpo real del documento.
7. **[PASO 7] Wiki-Links:** Se rastrea el cuerpo del documento buscando `[[...]]` para convertirlos en hipervínculos que apunten nuevamente a `view_file.php`, permitiendo la navegación fluida entre documentos.
8. **[PASO 8] Renderizado de Moodle:** Utiliza el método nativo de Moodle `format_text(FORMAT_MARKDOWN)` para asegurar la sanidad del HTML generado desde el Markdown.
9. **[PASO 9] UI de Metadatos:** Transforma las *tags*, *claims* (afirmaciones) y descripciones en la ficha visual encabezada con el tipo de documento (Concept, Entity, Playbook, etc.).
10. **[PASO 10] Entrega:** Combina todo, añade el botón "Ver en GitLab/GitHub" y, si está habilitado, el botón para abrir con Obsidian localmente, y lo imprime.

## Funciones Principales

### `gmv_parse_frontmatter`
Función personalizada que utiliza expresiones regulares avanzadas para detectar delimitadores `---` e iterar línea a línea construyendo un array asociativo del YAML, tolerando sintaxis de arrays inline `[a,b]` y listas `- elemento`.

```php
--8<-- "gitmetrics/view_file.php:gmv_parse_frontmatter"
```

### `gmv_convert_wiki_links`
Busca todas las ocurrencias de enlaces cruzados estilo Roam Research / Obsidian, reemplazándolos con una URL raw inyectable que mantendrá a los usuarios en la interfaz del plugin (`view_file.php?path=...`).

```php
--8<-- "gitmetrics/view_file.php:gmv_convert_wiki_links"
```

### `gmv_render_meta_card`
Componente visual embebido. Interroga las claves del array de metadatos (como el `type` OKF) para generar un cuadro visual (HTML y estilos inline) que se ancla en la cabecera de la vista de lectura.

```php
--8<-- "gitmetrics/view_file.php:gmv_render_meta_card"
```
