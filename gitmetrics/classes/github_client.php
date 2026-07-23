<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->libdir . '/filelib.php');

/**
 * Cliente HTTP para la API de GitHub y raw.githubusercontent.com.
 *
 * Usa la clase curl de Moodle (lib/filelib.php) para respetar la
 * configuración de proxy del servidor y las restricciones de red.
 *
 * Endpoints utilizados:
 *   - GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
 *     → árbol completo de ficheros y directorios.
 *   - GET https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}
 *     → contenido raw de cada fichero Markdown.
 */
class github_client implements git_provider_interface {

    const API_BASE = 'https://api.github.com';
    const RAW_BASE = 'https://raw.githubusercontent.com';

    /** @var string Token de autenticación (vacío = sin auth) */
    private string $token;

    public function __construct(string $token = '') {
        $this->token = $token;
    }

    // ---------------------------------------------------------------------
    // Métodos públicos
    // ---------------------------------------------------------------------

    /**
     * Obtiene el árbol recursivo de ficheros de un repositorio.
     *
     * @param  string $owner  Propietario del repo (ej. 'julia8873')
     * @param  string $repo   Nombre del repo (ej. 'bdc-prueba')
     * @param  string $branch Rama (ej. 'main')
     * @return array  Array de nodos [{path, type, size, sha, url}, ...]
     * @throws \Exception si la API devuelve error
     */
    public function get_tree(string $owner, string $repo, string $branch): array {
        $url      = self::API_BASE . "/repos/{$owner}/{$repo}/git/trees/{$branch}?recursive=1";
        $response = $this->api_request($url);

        if (!isset($response['tree'])) {
            throw new \Exception(get_string('error_branch', 'block_gitmetrics'));
        }

        // GitHub trunca árboles muy grandes; informar al caller
        if (!empty($response['truncated'])) {
            debugging('block_gitmetrics: el árbol del repo fue truncado por la API (> 100 000 elementos).', DEBUG_DEVELOPER);
        }

        return $response['tree'];
    }

    /**
     * Descarga el contenido raw de un fichero del repositorio.
     *
     * @param  string $owner
     * @param  string $repo
     * @param  string $path   Ruta relativa dentro del repo (ej. 'okf/index.md')
     * @param  string $branch
     * @return string Contenido del fichero (puede estar vacío)
     */
    public function get_file_content(string $owner, string $repo, string $path, string $branch): string {
        // Codificamos cada segmento del path por separado para no romper las '/'
        $encoded_path = implode('/', array_map('rawurlencode', explode('/', $path)));
        $url = self::RAW_BASE . "/{$owner}/{$repo}/{$branch}/{$encoded_path}";

        return $this->raw_request($url);
    }

    // ---------------------------------------------------------------------
    // Métodos privados de transporte HTTP
    // ---------------------------------------------------------------------

    /**
     * Petición a la API REST de GitHub (devuelve array descodificado de JSON).
     */
    private function api_request(string $url): array {
        $curl = new \curl(['ignoresecurity' => true]);
        $curl->setHeader($this->build_headers([
            'Accept: application/vnd.github.v3+json',
        ]));

        $raw = $curl->get($url);

        $http_code = $curl->get_info()['http_code'] ?? 0;

        if ($curl->get_errno()) {
            throw new \Exception('cURL error: ' . $curl->error);
        }

        $data = json_decode($raw, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new \Exception(get_string('error_json', 'block_gitmetrics'));
        }

        // La API devuelve {"message": "..."} en errores
        if (isset($data['message'])) {
            if ($http_code === 404) {
                throw new \Exception(get_string('error_repo', 'block_gitmetrics'));
            }
            if ($http_code === 403 && str_contains($data['message'], 'rate limit')) {
                throw new \Exception('GitHub API rate limit exceeded. Configure a token in the plugin global settings.');
            }
            throw new \Exception('GitHub API: ' . $data['message']);
        }

        return $data;
    }

    /**
     * Descarga raw (texto plano) sin decodificar JSON.
     */
    private function raw_request(string $url): string {
        $curl = new \curl(['ignoresecurity' => true]);
        $curl->setHeader($this->build_headers());

        $content   = $curl->get($url);
        $http_code = $curl->get_info()['http_code'] ?? 0;

        if ($curl->get_errno()) {
            // No lanzamos excepción aquí: un fichero inaccesible se trata como vacío.
            debugging('block_gitmetrics: no se pudo descargar ' . $url . ' (' . $curl->error . ')', DEBUG_DEVELOPER);
            return '';
        }

        if ($http_code !== 200) {
            debugging('block_gitmetrics: HTTP ' . $http_code . ' al descargar ' . $url, DEBUG_DEVELOPER);
            return '';
        }

        return $content;
    }

    /**
     * Construye los headers HTTP comunes.
     */
    private function build_headers(array $extra = []): array {
        $headers = array_merge([
            'User-Agent: Moodle-GitMetrics-Plugin/1.0',
        ], $extra);

        if (!empty($this->token)) {
            $headers[] = 'Authorization: Bearer ' . $this->token;
        }

        return $headers;
    }
}
