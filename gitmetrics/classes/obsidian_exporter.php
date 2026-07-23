<?php
// -----------------------------------------------------------------------------
// classes/obsidian_exporter.php
//
// Módulo de exportación a Obsidian.
//
// Este archivo es completamente independiente del resto del plugin.
// Para DESACTIVAR la integración con Obsidian:
//   1. Elimina este archivo.
//   2. Elimina cli/export_obsidian.php.
//   3. Elimina la sección "Obsidian" de settings.php (marcada con el comentario
//      "--- Sección Obsidian".
//   4. Elimina los botones "Abrir en Obsidian" de cli/setup_course.php
//      (marcados con el comentario "OBSIDIAN_OPTIONAL").
//
// Funcionamiento:
//   1. Descarga todos los archivos .md del repositorio Git remoto via API
//      (sin almacenarlos en la base de datos de Moodle).
//   2. Los escribe en una carpeta local del sistema de archivos que actúa
//      como vault de Obsidian (configurada en Ajustes del plugin).
//   3. Resuelve los [[wiki-links]] internos del repo a la notación nativa
//      de Obsidian (sin extensión, usando nombre de archivo base).
//   4. Guarda/sobreescribe únicamente los archivos que han cambiado para
//      no disparar modificaciones innecesarias en el vault.
//
// -----------------------------------------------------------------------------
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

/**
 * obsidian_exporter
 *
 * Descarga los documentos Markdown de un repositorio Git remoto y los
 * sincroniza con un vault local de Obsidian en el sistema de archivos.
 *
 * Ver la cabecera de este archivo
 * para instrucciones de eliminación limpia.
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

    /**
     * Ejecuta la exportación completa del repositorio al vault de Obsidian.
     *
     * Itera por todos los archivos .md del repositorio, descarga su contenido
     * raw, resuelve los wiki-links a formato Obsidian y los escribe en el vault.
     *
     * @return array Estadísticas de la exportación: ['written' => int, 'skipped' => int, 'errors' => string[]]
     */
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

    /**
     * Transforma los [[wiki-links]] del repositorio al formato nativo de Obsidian.
     *
     * Los wiki-links del repositorio OKF tienen la forma:
     *   [[okf/entities/jose-juan-urrutia-milan|Texto visible]]
     *   [[okf/concepts/lema-de-gronwall]]
     *
     * Obsidian los entiende como:
     *   [[jose-juan-urrutia-milan|Texto visible]]   (solo nombre de archivo base, sin extensión ni ruta)
     *   [[lema-de-gronwall]]
     *
     * @param  string $content Contenido Markdown raw del repositorio.
     * @return string          Contenido con wiki-links resueltos al formato Obsidian.
     */
    private function resolve_wikilinks(string $content): string {
        // Patrón: [[ruta/completa/al-archivo|Texto opcional]]
        return preg_replace_callback(
            '/\[\[([^\]|]+)(\|([^\]]+))?\]\]/',
            function (array $m): string {
                $target_path  = trim($m[1]);          // ej. okf/entities/jose-juan-urrutia-milan
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
    public static function get_obsidian_uri(string $filepath, string $vault_name): string {
        // Eliminar extensión .md porque Obsidian la infiere automáticamente
        $file_without_ext = preg_replace('/\.md$/i', '', $filepath);

        return 'obsidian://open?vault=' . rawurlencode($vault_name)
             . '&file='  . rawurlencode($file_without_ext);
    }
}
