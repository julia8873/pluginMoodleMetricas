<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->libdir . '/filelib.php');

/**
 * Cliente HTTP para la API v4 de GitLab (auto-alojado u OSL).
 *
 * Compatible con cualquier instancia GitLab: la OSL de tu universidad,
 * un servidor GitLab en red local o el propio gitlab.com.
 *
 * Endpoints utilizados:
 *   - GET /api/v4/projects/{id_encoded}/repository/tree?recursive=true&ref={branch}
 *     → arbol completo de ficheros y directorios.
 *   - GET /api/v4/projects/{id_encoded}/repository/files/{path_encoded}/raw?ref={branch}
 *     → contenido raw de cada fichero Markdown.
 *
 * Autenticacion:
 *   - Token personal (PRIVATE-TOKEN) o token de acceso de proyecto.
 *   - Sin token funciona para repositorios publicos.
 */
class gitlab_client implements git_provider_interface {

    /** @var string URL base de la instancia GitLab (sin barra final). Ej: https://gitlab.osl.ugr.es */
    private string $base_url;

    /** @var string Token de acceso (PRIVATE-TOKEN). Vacio = sin autenticacion. */
    private string $token;

    /**
     * @param string $base_url URL base del servidor GitLab (sin barra final).
     *                         Ejemplos:
     *                           - 'https://gitlab.com'
     *                           - 'https://gitlab.osl.ugr.es'
     *                           - 'http://localhost:8929'
     * @param string $token    Token personal o de proyecto de GitLab (PRIVATE-TOKEN).
     */
    public function __construct(string $base_url = 'https://gitlab.com', string $token = '') {
        $this->base_url = rtrim($base_url, '/');
        $this->token    = $token;
    }

    // -------------------------------------------------------------------------
    // Implementacion de git_provider_interface
    // -------------------------------------------------------------------------

    /**
     * Obtiene el arbol recursivo del repositorio via API v4 de GitLab.
     *
     * GitLab devuelve los nodos paginados (max 100 por pagina), por lo que
     * este metodo itera todas las paginas hasta recopilarlos todos.
     */
    public function get_tree(string $owner, string $repo, string $branch): array {
        $project_id = rawurlencode("{$owner}/{$repo}");
        $nodes      = [];
        $page       = 1;
        $per_page   = 100;

        do {
            $url      = $this->base_url
                      . "/api/v4/projects/{$project_id}/repository/tree"
                      . "?recursive=true&ref=" . rawurlencode($branch)
                      . "&per_page={$per_page}&page={$page}";
            $response = $this->api_request($url);

            if (!is_array($response)) {
                throw new \Exception(get_string('error_branch', 'block_gitmetrics'));
            }

            foreach ($response as $item) {
                // Normalizar al mismo esquema que usa github_client
                $nodes[] = [
                    'path' => $item['path']    ?? '',
                    'type' => ($item['type'] === 'blob') ? 'blob' : 'tree',
                    'size' => $item['id'] ? 0 : 0, // size no viene en el arbol; se recupera en get_file_content
                    'sha'  => $item['id']      ?? '',
                    'mode' => $item['mode']    ?? '',
                ];
            }

            $page++;
        } while (count($response) === $per_page);

        if (empty($nodes)) {
            throw new \Exception(get_string('error_branch', 'block_gitmetrics'));
        }

        return $nodes;
    }

    /**
     * Descarga el contenido raw de un fichero via API v4 de GitLab.
     */
    public function get_file_content(string $owner, string $repo, string $path, string $branch): string {
        $project_id   = rawurlencode("{$owner}/{$repo}");
        $encoded_path = rawurlencode($path);
        $url = $this->base_url
             . "/api/v4/projects/{$project_id}/repository/files/{$encoded_path}/raw"
             . "?ref=" . rawurlencode($branch);

        return $this->raw_request($url);
    }

    // -------------------------------------------------------------------------
    // Metodos privados de transporte HTTP
    // -------------------------------------------------------------------------

    /**
     * Peticion a la API REST de GitLab (devuelve array decodificado de JSON).
     */
    private function api_request(string $url): array {
        $curl = new \curl(['ignoresecurity' => true]);
        $curl->setHeader($this->build_headers());

        $raw       = $curl->get($url);
        $http_code = $curl->get_info()['http_code'] ?? 0;

        if ($curl->get_errno()) {
            throw new \Exception('cURL error: ' . $curl->error);
        }

        $data = json_decode($raw, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new \Exception(get_string('error_json', 'block_gitmetrics'));
        }

        // GitLab devuelve {"message": "..."} en errores
        if (isset($data['message'])) {
            if ($http_code === 404) {
                throw new \Exception(get_string('error_repo', 'block_gitmetrics'));
            }
            throw new \Exception('GitLab API: ' . $data['message']);
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
            debugging('block_gitmetrics (GitLab): no se pudo descargar ' . $url . ' (' . $curl->error . ')', DEBUG_DEVELOPER);
            return '';
        }

        if ($http_code !== 200) {
            debugging('block_gitmetrics (GitLab): HTTP ' . $http_code . ' al descargar ' . $url, DEBUG_DEVELOPER);
            return '';
        }

        return $content;
    }

    /**
     * Construye los headers HTTP comunes para GitLab.
     * GitLab usa PRIVATE-TOKEN en lugar de Authorization: Bearer.
     */
    private function build_headers(): array {
        $headers = ['User-Agent: Moodle-GitMetrics-Plugin/1.0'];

        if (!empty($this->token)) {
            $headers[] = 'PRIVATE-TOKEN: ' . $this->token;
        }

        return $headers;
    }
}
