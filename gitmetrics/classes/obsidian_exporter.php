<?php
// -----------------------------------------------------------------------------
// classes/obsidian_exporter.php
//
// Módulo de exportación a Obsidian.
//
// -----------------------------------------------------------------------------
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

/*
--8<-- [start:class_desc]
Descarga los documentos Markdown de un repositorio Git remoto y los
sincroniza con un vault local de Obsidian en el sistema de archivos,
resolviendo además los enlaces internos (`[[wiki-links]]`) para que
sean compatibles con el cliente nativo de Obsidian.
--8<-- [end:class_desc]
*/
class obsidian_exporter {

    /** @var string Ruta absoluta local del vault de Obsidian donde se escribirán los archivos */
    private string $vault_path;

    /** @var git_provider_interface Cliente del proveedor Git (GitHub o GitLab) */
    private git_provider_interface $git_client;

    /** @var string Propietario del repositorio (owner o grupo) */
    private string $owner;

    /** @var string Nombre del repositorio */
    private string $repo;

    /** @var string Rama del repositorio a exportar */
    private string $branch;

    /**
     * Constructor.
     *
     * @param git_provider_interface $git_client  Cliente ya instanciado (github_client o gitlab_client).
     * @param string                 $repourl     URL completa del repositorio (ej. https://gitlab.com/owner/repo).
     * @param string                 $vault_path  Ruta absoluta en el sistema de archivos local donde vive el vault de Obsidian.
     * @param string                 $branch      Rama Git a exportar (default: 'main').
     */
    // --8<-- [start:construct]
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
    // --8<-- [end:construct]

    /**
     * Ejecuta la exportación completa del repositorio al vault de Obsidian.
     *
     * Itera por todos los archivos .md del repositorio, descarga su contenido
     * raw, resuelve los wiki-links a formato Obsidian y los escribe en el vault.
     *
     * @return array Estadísticas de la exportación: ['written' => int, 'skipped' => int, 'errors' => string[]]
     */
    // --8<-- [start:export]
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
    // --8<-- [end:export]

    /**
     * Transforma los [[wiki-links]] del repositorio al formato nativo de Obsidian.
     *
     * Los wiki-links del repositorio OKF tienen la forma:
     *   [[okf/entities/juan-perez-ejemplo|Texto visible]]
     *   [[okf/concepts/lema-de-gronwall]]
     *
     * Obsidian los entiende como:
     *   [[juan-perez-ejemplo|Texto visible]]   (solo nombre de archivo base, sin extensión ni ruta)
     *   [[lema-de-gronwall]]
     *
     * @param  string $content Contenido Markdown raw del repositorio.
     * @return string          Contenido con wiki-links resueltos al formato Obsidian.
     */
    // --8<-- [start:resolve_wikilinks]
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
    // --8<-- [end:resolve_wikilinks]

    /**
     * Genera la URI de protocolo obsidian:// para abrir un archivo específico
     * directamente en la aplicación Obsidian del escritorio.
     *
     * El formato es:
     *   obsidian://open?vault=NombreDelVault&file=ruta/relativa/al/archivo
     *
     * @param  string $filepath     Ruta relativa del archivo dentro del repositorio (ej. okf/concepts/lema.md).
     * @param  string $vault_name   Nombre del vault tal y como Obsidian lo conoce (nombre de la carpeta).
     * @return string               URI de protocolo obsidian:// lista para usar en un enlace HTML.
     */
    // --8<-- [start:get_obsidian_uri]
    public static function get_obsidian_uri(string $filepath, string $vault_name): string {
        // Eliminar extensión .md porque Obsidian la infiere automáticamente
        $file_without_ext = preg_replace('/\.md$/i', '', $filepath);

        return 'obsidian://open?vault=' . rawurlencode($vault_name)
             . '&file='  . rawurlencode($file_without_ext);
    }
    // --8<-- [end:get_obsidian_uri]
}
