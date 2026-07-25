Crear archivo en: `docs/gitmetrics/view_file.md`

# Archivo `view_file`

Ubicación: `view_file.php`

```python
Visor de archivos Markdown en vivo desde el repositorio Git.

Características:
 · Parsea frontmatter YAML y lo renderiza como ficha elegante
 · Convierte [[wiki-links]] de estilo Obsidian en hipervínculos Moodle
 · Renderiza el cuerpo Markdown con format_text
 · No almacena ningún archivo en disco — todo en memoria RAM
```

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
```python
function gmv_parse_frontmatter(string $content): array {
    $meta = [];
    $body = $content;

    if (preg_match('/^---\s*\n(.*?)\n---\s*\n?(.*)/s', $content, $m)) {
        $yaml = $m[1];
        $body = ltrim($m[2]);
        // Parsear campo a campo
        $lines   = explode("\n", $yaml);
        $cur_key = null;
        foreach ($lines as $line) {
            if (trim($line) === '') continue;
            // Lista inline: key: [a, b, c]
            if (preg_match('/^([a-zA-Z_][a-zA-Z0-9_]*):\s*\[([^\]]*)\]\s*$/', $line, $lm)) {
                $cur_key       = $lm[1];
                $raw_arr       = trim($lm[2]);
                $meta[$cur_key] = $raw_arr === ''
                    ? []
                    : array_map('trim', explode(',', $raw_arr));
                continue;
            }
            // Clave escalar: key: value
            if (preg_match('/^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)?$/', $line, $lm)) {
                $cur_key        = $lm[1];
                $val            = trim($lm[2] ?? '');
                $meta[$cur_key] = $val;
                continue;
            }
            // Elemento de lista YAML: - item
            if ($cur_key && preg_match('/^\s+-\s+(.+)$/', $line, $lm)) {
                if (!is_array($meta[$cur_key])) $meta[$cur_key] = [];
                $meta[$cur_key][] = trim($lm[1]);
            }
        }
    }
    return ['meta' => $meta, 'body' => $body];
}
// 
```


### `gmv_convert_wiki_links`
Busca todas las ocurrencias de enlaces cruzados estilo Roam Research / Obsidian, reemplazándolos con una URL raw inyectable que mantendrá a los usuarios en la interfaz del plugin (`view_file.php?path=...`).

```php
```python
function gmv_convert_wiki_links(string $body, string $repourl, string $branch, int $courseid, int $blockid): string {
    // Directorio base del archivo actual (para resolver paths relativos)
    // No lo necesitamos aquí porque los wiki-links suelen ser paths completos

    $replace = function(array $m) use ($repourl, $branch, $courseid, $blockid): string {
        // $m[1] = path, $m[2] = texto (si existe)
        $wpath   = trim($m[1]);
        $display = isset($m[2]) ? trim($m[2]) : basename($wpath);
        // Añadir extensión .md si no la tiene
        if (!str_ends_with(strtolower($wpath), '.md')) {
            $wpath .= '.md';
        }
        $url = (new moodle_url('/blocks/gitmetrics/view_file.php', [
            'courseid' => $courseid,
            'blockid'  => $blockid,
            'path'     => $wpath,
            'repo_url' => $repourl,
            'branch'   => $branch,
        ]))->out(false); // out(false) → raw URL para embeber en Markdown
        return '[' . $display . '](' . $url . ')';
    };

    // [[path|Texto de enlace]]
    $body = preg_replace_callback('/\[\[([^\]|#]+)(?:#[^\]|]*)?\|([^\]]+)\]\]/', $replace, $body);
    // [[path]] sin texto
    $body = preg_replace_callback('/\[\[([^\]|#]+)(?:#[^\]|]*)?\]\]/', function($m) use ($replace) {
        return $replace([$m[0], $m[1]]);
    }, $body);

    return $body;
}
// 
```


### `gmv_render_meta_card`
Componente visual embebido. Interroga las claves del array de metadatos (como el `type` OKF) para generar un cuadro visual (HTML y estilos inline) que se ancla en la cabecera de la vista de lectura.

```php
```python
function gmv_render_meta_card(array $meta, string $repourl, string $branch, int $courseid, int $blockid): string {
    if (empty($meta)) return '';

    // Icono por tipo de documento OKF
    $type_config = [
        'Concept'  => ['[C]', '#7c3aed', '#ede9fe'],
        'Entity'   => ['[E]', '#0f766e', '#ccfbf1'],
        'Source'   => ['[S]', '#b45309', '#fef3c7'],
        'Index'    => ['[I]', '#1e40af', '#dbeafe'],
        'Log'      => ['[L]', '#374151', '#f3f4f6'],
        'Playbook' => ['[P]', '#be185d', '#fce7f3'],
    ];
    $type      = $meta['type'] ?? '';
    $tc        = $type_config[$type] ?? ['[D]', '#334155', '#f1f5f9'];
    $icon      = $tc[0]; $color = $tc[1]; $bg = $tc[2];

    $title       = $meta['title']       ?? '';
    $description = $meta['description'] ?? '';
    $tags        = (array)($meta['tags'] ?? []);
    $timestamp   = $meta['timestamp']   ?? '';
    $resource    = $meta['resource']    ?? '';
    $claims      = (array)($meta['claims'] ?? []);

    $h  = '<div class="gmv-meta-card">';

    // Cabecera tipo + título
    $h .= '<div class="gmv-meta-header" style="background:' . $bg . ';border-left:4px solid ' . $color . ';">';
    if ($type) {
        $h .= '<span class="gmv-meta-type" style="color:' . $color . ';">' . $icon . ' ' . htmlspecialchars($type) . '</span>';
    }
    if ($title) {
        $h .= '<h1 class="gmv-meta-title">' . htmlspecialchars($title) . '</h1>';
    }
    $h .= '</div>';

    // Descripción
    if ($description) {
        $h .= '<div class="gmv-meta-desc">' . htmlspecialchars($description) . '</div>';
    }

    // Recurso relacionado (con wiki-link si contiene path)
    if ($resource) {
        $res_path = trim($resource);
        if (!str_ends_with(strtolower($res_path), '.md')) $res_path .= '.md';
        $res_url = (new moodle_url('/blocks/gitmetrics/view_file.php', [
            'courseid' => $courseid,
            'blockid'  => $blockid,
            'path'     => $res_path,
            'repo_url' => $repourl,
            'branch'   => $branch,
        ]))->out();
        $h .= '<div class="gmv-meta-row">';
        $h .= '<span class="gmv-meta-label">Recurso:</span>';
        $h .= '<a href="' . $res_url . '" class="gmv-meta-link">' . htmlspecialchars(basename($res_path)) . '</a>';
        $h .= '</div>';
    }

    // Tags
    if (!empty($tags)) {
        $tags_clean = array_filter(array_map('trim', $tags));
        if (!empty($tags_clean)) {
            $h .= '<div class="gmv-meta-row gmv-meta-tags">';
            $h .= '<span class="gmv-meta-label">Tags:</span>';
            foreach ($tags_clean as $tag) {
                $h .= '<span class="gmv-tag">' . htmlspecialchars($tag) . '</span>';
            }
            $h .= '</div>';
        }
    }

    // Claims
    if (!empty($claims)) {
        $claims_clean = array_filter(array_map('trim', $claims));
        if (!empty($claims_clean)) {
            $h .= '<div class="gmv-meta-row">';
            $h .= '<span class="gmv-meta-label">Afirmaciones:</span>';
            $h .= '<ul class="gmv-claims-list">';
            foreach ($claims_clean as $claim) {
                $h .= '<li>' . htmlspecialchars($claim) . '</li>';
            }
            $h .= '</ul>';
            $h .= '</div>';
        }
    }

    // Timestamp
    if ($timestamp) {
        try {
            $ts = new DateTime($timestamp);
            $ts_fmt = $ts->format('d/m/Y H:i');
        } catch (\Exception $e) {
            $ts_fmt = $timestamp;
        }
        $h .= '<div class="gmv-meta-ts">Actualizado: ' . htmlspecialchars($ts_fmt) . '</div>';
    }

    $h .= '</div>';
    return $h;
}
// 
```

