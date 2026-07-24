# Clase `obsidian_exporter`

Ubicación: `classes/obsidian_exporter.php`

```python
Descarga los documentos Markdown de un repositorio Git remoto y los
sincroniza con un vault local de Obsidian en el sistema de archivos,
resolviendo además los enlaces internos (`[[wiki-links]]`) para que
sean compatibles con el cliente nativo de Obsidian.
```

## Diagrama de Flujo Principal

```mermaid
graph TD
    A["1. Iniciar Exportación"] --> B["2. Obtener árbol remoto completo"]
    B --> C["3. Filtrar archivos .md"]
    C --> D{"¿Quedan archivos?"}
    D -- No --> E["Fin: Devolver estadísticas"]
    D -- Sí --> F["4. Descargar contenido raw"]
    F --> G["5. Resolver wiki-links a Obsidian"]
    G --> H["6. Generar ruta destino local"]
    H --> I{"¿Ha cambiado el contenido?"}
    I -- Sí --> J["7. Escribir/Sobrescribir archivo en disco"]
    I -- No --> K["8. Saltar archivo"]
    J --> D
    K --> D
```

### Detalle de los Pasos del Flujo

1. **[PASO 1] Iniciar Exportación:** Se invoca el método `export()` con los datos del repositorio y el cliente de Git ya inicializado.
2. **[PASO 2] Obtener árbol remoto completo:** A través del API de GitHub/GitLab, se solicita la lista recursiva de todos los archivos del repositorio en la rama indicada.
3. **[PASO 3] Filtrar archivos .md:** Se descartan todos los ficheros que no sean blobs con extensión `.md`.
4. **[PASO 4] Descargar contenido raw:** Para cada fichero Markdown encolado, se descarga su contenido de texto desde el repositorio a la memoria temporal (sin pasar por la BD de Moodle).
5. **[PASO 5] Resolver wiki-links a Obsidian:** Se analiza el texto usando expresiones regulares para convertir enlaces largos (ej: `[[carpeta/archivo|Texto]]`) en enlaces cortos nativos de Obsidian (`[[archivo|Texto]]`).
6. **[PASO 6] Generar ruta destino local:** Se calcula en qué subcarpeta del vault local de Obsidian debe guardarse el fichero, creando los directorios intermedios si no existen.
7. **[PASO 7] Escribir/Sobrescribir archivo en disco:** Si el contenido parseado difiere de lo que ya hay en el disco duro, se sobrescribe físicamente.
8. **[PASO 8] Saltar archivo:** Si el contenido es idéntico, se evita la escritura para no alterar las fechas de modificación del vault local.

## Funciones Principales

### `__construct`
Constructor de la clase. Recibe la URL del repositorio, el cliente de Git instanciado y extrae el *owner* y el *repo* necesarios para las llamadas a la API.

```php
```python
public function __construct(
    git_provider_interface $git_client,
    string $repourl,
    string $vault_path,
    string $branch = 'main'
) {
    $this->git_client = $git_client;
    $this->vault_path = rtrim($vault_path, '/\\');
    $this->branch     = $branch;

    // Extraer owner y repo de la URL
    $parsed     = parse_url($repourl);
    $path_parts = array_values(array_filter(explode('/', trim($parsed['path'] ?? '', '/'))));
    if (count($path_parts) < 2) {
        throw new \moodle_exception('error_invalid_url', 'block_gitmetrics');
    }
    $this->owner = $path_parts[0];
    $this->repo  = $path_parts[1];
}
// 
```


### `export`
Ejecuta la exportación completa iterando sobre todos los archivos `.md`, procesándolos y guardándolos localmente. Devuelve estadísticas sobre los ficheros escritos, saltados o con errores.

```php
```python
public function export(): array {
    $stats = ['written' => 0, 'skipped' => 0, 'errors' => []];

    // Obtener árbol completo del repositorio
    $tree = $this->git_client->get_tree($this->owner, $this->repo, $this->branch);

    // Filtrar solo archivos Markdown
    $md_files = array_filter($tree, function (array $node): bool {
        return $node['type'] === 'blob'
            && str_ends_with(strtolower($node['path']), '.md');
    });

    foreach ($md_files as $node) {
        $filepath = $node['path'];

        try {
            // Descargar contenido raw desde la API (en memoria, sin escribir en Moodle)
            $raw_content = $this->git_client->get_file_content(
                $this->owner, $this->repo, $filepath, $this->branch
            );

            // Transformar los [[wiki-links]] al formato nativo de Obsidian
            $obsidian_content = $this->resolve_wikilinks($raw_content);

            // Calcular ruta destino dentro del vault, manteniendo la estructura de carpetas del repo
            $target_path = $this->vault_path . DIRECTORY_SEPARATOR
                . str_replace('/', DIRECTORY_SEPARATOR, $filepath);

            // Crear carpetas intermedias si no existen
            $target_dir = dirname($target_path);
            if (!is_dir($target_dir)) {
                mkdir($target_dir, 0755, true);
            }

            // Escribir solo si el contenido ha cambiado (evita modificar timestamps innecesariamente)
            $existing = is_file($target_path) ? file_get_contents($target_path) : null;
            if ($existing !== $obsidian_content) {
                file_put_contents($target_path, $obsidian_content, LOCK_EX);
                $stats['written']++;
            } else {
                $stats['skipped']++;
            }

        } catch (\Throwable $e) {
            $stats['errors'][] = "[ERROR] {$filepath}: " . $e->getMessage();
        }
    }

    return $stats;
}
// 
```


### `resolve_wikilinks`
Transforma los `[[wiki-links]]` del estándar de repositorio OKF al formato plano nativo de Obsidian (extrayendo únicamente el *basename* de cada archivo).

```php
```python
private function resolve_wikilinks(string $content): string {
    // Patrón: [[ruta/completa/al-archivo|Texto opcional]]
    return preg_replace_callback(
        '/\[\[([^\]|]+)(\|([^\]]+))?\]\]/',
        function (array $m): string {
            $target_path  = trim($m[1]);          // ej. okf/entities/juan-perez-ejemplo
            $display_text = $m[3] ?? '';           // texto después de | (puede estar vacío)

            // Extraer solo el nombre base del archivo sin extensión (formato Obsidian nativo)
            $basename = pathinfo($target_path, PATHINFO_FILENAME);
            // Si el path no tenía extensión, pathinfo devuelve el propio basename
            if ($basename === '') {
                $basename = basename($target_path);
            }

            // Reconstruir como link Obsidian nativo
            if ($display_text !== '') {
                return "[[{$basename}|{$display_text}]]";
            }
            return "[[{$basename}]]";
        },
        $content
    );
}
// 
```


### `get_obsidian_uri`
Método estático de utilidad para construir una URL de protocolo `obsidian://` que permite abrir una nota específica directamente en la aplicación de escritorio.

```php
```python
public static function get_obsidian_uri(string $filepath, string $vault_name): string {
    // Eliminar extensión .md porque Obsidian la infiere automáticamente
    $file_without_ext = preg_replace('/\.md$/i', '', $filepath);

    return 'obsidian://open?vault=' . rawurlencode($vault_name)
         . '&file='  . rawurlencode($file_without_ext);
}
// 
```

