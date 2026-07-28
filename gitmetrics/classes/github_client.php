<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->libdir . '/filelib.php');

/*
--8<-- [start:class_desc]
Cliente HTTP para la API de GitHub y raw.githubusercontent.com.

Usa la clase curl de Moodle (lib/filelib.php) para respetar la
configuracion de proxy del servidor y las restricciones de red.

Endpoints de lectura:
  - GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
    -> arbol completo de ficheros y directorios.
  - GET https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}
    -> contenido raw de cada fichero Markdown.

Endpoints de escritura (aprovisionamiento de repos de alumno):
  - POST /repos/{template_owner}/{template_repo}/generate
    -> crea un repo a partir de una plantilla (create_repo_from_template).
  - POST /repos/{source_owner}/{source_repo}/forks
    -> hace fork de un repo y lo renombra (fork_repo).
  - PUT /repos/{owner}/{repo}/collaborators/{username}
    -> añade un colaborador con permiso dado (add_collaborator).
--8<-- [end:class_desc]
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
     * @param  string $owner  Propietario del repo (ej. '<tu_usuario>')
     * @param  string $repo   Nombre del repo (ej. 'bdc-prueba')
     * @param  string $branch Rama (ej. 'main')
     * @return array  Array de nodos [{path, type, size, sha, url}, ...]
     * @throws \Exception si la API devuelve error
     */
    // --8<-- [start:get_tree]
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
    // --8<-- [end:get_tree]

    /**
     * Descarga el contenido raw de un fichero del repositorio.
     *
     * @param  string $owner
     * @param  string $repo
     * @param  string $path   Ruta relativa dentro del repo (ej. 'okf/index.md')
     * @param  string $branch
     * @return string Contenido del fichero (puede estar vacío)
     */
    // --8<-- [start:get_file_content]
    public function get_file_content(string $owner, string $repo, string $path, string $branch): string {
        // Codificamos cada segmento del path por separado para no romper las '/'
        $encoded_path = implode('/', array_map('rawurlencode', explode('/', $path)));
        $url = self::RAW_BASE . "/{$owner}/{$repo}/{$branch}/{$encoded_path}";

        return $this->raw_request($url);
    }
    // --8<-- [end:get_file_content]

    // ---------------------------------------------------------------------
    // Métodos de escritura (aprovisionamiento de repos de alumno)
    // ---------------------------------------------------------------------

    /**
     * Crea un repositorio a partir de una plantilla GitHub.
     *
     * Usa el endpoint POST /repos/{template_owner}/{template_repo}/generate
     * (requiere scope 'repo' en el token).
     * Si el repo ya existe (HTTP 422), lanza excepcion con mensaje claro
     * para que el caller pueda detectar el caso de idempotencia.
     *
     * @param  string $template_owner  Propietario del repo plantilla
     * @param  string $template_repo   Nombre del repo plantilla
     * @param  string $new_namespace   Cuenta u org GitHub donde crear el repo
     * @param  string $new_name        Nombre del repo nuevo
     * @return string URL HTML del repo creado (html_url del objeto devuelto)
     * @throws \Exception Si la API devuelve error
     */
    // --8<-- [start:create_repo_from_template]
    public function create_repo_from_template(
        string $template_owner,
        string $template_repo,
        string $new_namespace,
        string $new_name
    ): string {
        $url     = self::API_BASE . "/repos/{$template_owner}/{$template_repo}/generate";
        $payload = [
            'owner'       => $new_namespace,
            'name'        => $new_name,
            'private'     => true,
            'description' => 'Base de Conocimiento personal generada por GitMetrics',
        ];

        $data = $this->api_post($url, $payload, [
            // Endpoint de "Generate from template" requiere este media type
            'Accept: application/vnd.github.baptiste-preview+json',
        ]);

        if (empty($data['html_url'])) {
            throw new \Exception('GitHub API generate: respuesta inesperada — html_url ausente.');
        }

        return $data['html_url'];
    }
    // --8<-- [end:create_repo_from_template]

    /**
     * Hace fork de un repositorio existente en $target_namespace.
     *
     * Usa el endpoint POST /repos/{owner}/{repo}/forks y luego renombra
     * el fork via PATCH /repos/{namespace}/{fork_name} si el nombre por
     * defecto difiere del solicitado.
     *
     * Nota: la API de GitHub crea el fork de forma asincrona; puede tardar
     * unos segundos en estar disponible. Esta implementacion espera hasta
     * 10 segundos y devuelve la URL si el fork ya aparece.
     *
     * @param  string $source_owner     Propietario del repo origen
     * @param  string $source_repo      Nombre del repo origen
     * @param  string $target_namespace Cuenta u org donde crear el fork
     * @param  string $new_name         Nombre del fork
     * @return string URL HTML del fork creado
     * @throws \Exception Si la API devuelve error
     */
    // --8<-- [start:fork_repo]
    public function fork_repo(
        string $source_owner,
        string $source_repo,
        string $target_namespace,
        string $new_name
    ): string {
        if ($source_owner === $target_namespace) {
            // GitHub no permite hacer fork a la misma cuenta y el workaround de plantillas falla 
            // asincronamente si la plantilla a su vez fue generada desde otra plantilla.
            // Solución robusta: crear un repositorio vacío y hacer mirror push con git cli.
            
            $user_info = $this->api_request(self::API_BASE . "/users/{$target_namespace}");
            if (!empty($user_info['type']) && strtolower($user_info['type']) === 'organization') {
                $create_url = self::API_BASE . "/orgs/{$target_namespace}/repos";
            } else {
                $create_url = self::API_BASE . "/user/repos";
            }
            
            $payload = [
                'name' => $new_name,
                'private' => true,
                'description' => 'Base de Conocimiento personal generada por GitMetrics',
            ];
            $data = $this->api_post($create_url, $payload);
            
            if (empty($data['html_url'])) {
                throw new \Exception('GitHub API create: respuesta inesperada — html_url ausente.');
            }
            
            $token = $this->token;
            $source_clone_url = "https://x-access-token:{$token}@github.com/{$source_owner}/{$source_repo}.git";
            $dest_push_url = "https://x-access-token:{$token}@github.com/{$target_namespace}/{$new_name}.git";
            
            $tmp = sys_get_temp_dir() . '/' . uniqid('git_clone_');
            $cmd = sprintf(
                'git clone --bare %s %s 2>&1 && cd %s && git push --mirror %s 2>&1',
                escapeshellarg($source_clone_url),
                escapeshellarg($tmp),
                escapeshellarg($tmp),
                escapeshellarg($dest_push_url)
            );
            exec($cmd, $out, $ret);
            exec(sprintf('rm -rf %s', escapeshellarg($tmp)));
            
            if ($ret !== 0) {
                throw new \Exception("Fallo al copiar el repositorio usando git local: " . implode("\n", $out));
            }
            
            return $data['html_url'];
        }

        $url     = self::API_BASE . "/repos/{$source_owner}/{$source_repo}/forks";
        $payload = ['organization' => $target_namespace];

        // El fork se crea con el mismo nombre que el repo origen por defecto
        $data = $this->api_post($url, $payload);

        // Nombre real del fork en la respuesta (puede diferir de $new_name)
        $fork_name = $data['name'] ?? $source_repo;

        // Si el nombre no es el solicitado, renombramos via PATCH
        if ($fork_name !== $new_name) {
            $rename_url = self::API_BASE . "/repos/{$target_namespace}/{$fork_name}";
            $data       = $this->api_patch($rename_url, ['name' => $new_name]);
        }

        if (empty($data['html_url'])) {
            throw new \Exception('GitHub API fork: respuesta inesperada — html_url ausente.');
        }

        return $data['html_url'];
    }
    // --8<-- [end:fork_repo]

    /**
     * Añade un colaborador a un repositorio con el permiso indicado.
     *
     * Mapeo de roles semanticos a GitHub permissions:
     *   guest/reporter => 'pull'   (lectura)
     *   developer      => 'push'   (lectura + escritura)
     *   maintainer     => 'maintain'
     *   owner          => 'admin'
     *
     * Requiere scope 'repo' (cuenta personal) o 'write:org' (organizacion).
     * Un HTTP 201 indica invitation enviada; 204 indica ya era colaborador.
     *
     * @param  string $owner    Propietario del repo
     * @param  string $repo     Nombre del repo
     * @param  string $username Login GitHub del usuario
     * @param  string $role     Rol semantico (por defecto 'maintainer')
     * @return bool   true si se añadio o ya era colaborador
     * @throws \Exception Si la API devuelve un error no recuperable
     */
    // --8<-- [start:add_collaborator]
    public function add_collaborator(
        string $owner,
        string $repo,
        string $username,
        string $role = 'maintainer'
    ): bool {
        $permission_map = [
            'guest'      => 'pull',
            'reporter'   => 'pull',
            'developer'  => 'push',
            'maintainer' => 'maintain',
            'owner'      => 'admin',
        ];
        $permission = $permission_map[$role] ?? 'push';

        $url = self::API_BASE . "/repos/{$owner}/{$repo}/collaborators/{$username}";
        $this->api_put($url, ['permission' => $permission]);

        return true;
    }
    // --8<-- [end:add_collaborator]

    // ---------------------------------------------------------------------
    // Métodos privados de transporte HTTP
    // ---------------------------------------------------------------------

    /**
     * Petición GET a la API REST de GitHub (devuelve array descodificado de JSON).
     */
    private function api_request(string $url, array $extra_headers = []): array {
        $curl = new \curl(['ignoresecurity' => true]);
        $curl->setHeader($this->build_headers(array_merge([
            'Accept: application/vnd.github.v3+json',
        ], $extra_headers)));

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
     * Petición POST a la API REST de GitHub.
     *
     * @param  string $url
     * @param  array  $payload      Datos a enviar como JSON en el cuerpo
     * @param  array  $extra_headers Headers adicionales (p.ej. Accept de preview)
     * @return array  Respuesta decodificada
     * @throws \Exception En errores de red o de la API
     */
    private function api_post(string $url, array $payload, array $extra_headers = []): array {
        $curl = new \curl(['ignoresecurity' => true]);
        $curl->setHeader($this->build_headers(array_merge([
            'Accept: application/vnd.github.v3+json',
            'Content-Type: application/json',
        ], $extra_headers)));

        $raw       = $curl->post($url, json_encode($payload));
        $http_code = $curl->get_info()['http_code'] ?? 0;

        if ($curl->get_errno()) {
            throw new \Exception('cURL error (POST): ' . $curl->error);
        }

        // 201 Created, 202 Accepted (fork asíncrono) — ambos son éxito
        if ($http_code === 202 && empty($raw)) {
            return ['html_url' => ''];
        }

        $data = json_decode($raw, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new \Exception(get_string('error_json', 'block_gitmetrics'));
        }

        if (isset($data['message'])) {
            // 422 = repo ya existe
            if ($http_code === 422) {
                throw new \Exception('GitHub API: repo ya existe o nombre inválido — ' . $data['message']);
            }
            throw new \Exception('GitHub API (POST): ' . $data['message']);
        }

        return $data;
    }

    /**
     * Petición PATCH a la API REST de GitHub (para renombrar repos, etc.).
     */
    private function api_patch(string $url, array $payload): array {
        $curl = new \curl(['ignoresecurity' => true]);
        $curl->setHeader($this->build_headers([
            'Accept: application/vnd.github.v3+json',
            'Content-Type: application/json',
        ]));

        // Moodle curl no tiene método patch nativo; se simula con setopt
        $curl->setopt('CURLOPT_CUSTOMREQUEST', 'PATCH');
        $raw       = $curl->post($url, json_encode($payload));
        $http_code = $curl->get_info()['http_code'] ?? 0;

        if ($curl->get_errno()) {
            throw new \Exception('cURL error (PATCH): ' . $curl->error);
        }

        $data = json_decode($raw, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new \Exception(get_string('error_json', 'block_gitmetrics'));
        }

        if (isset($data['message'])) {
            throw new \Exception('GitHub API (PATCH): ' . $data['message']);
        }

        return $data;
    }

    /**
     * Petición PUT a la API REST de GitHub (para añadir colaboradores, etc.).
     * Acepta respuestas 201 (invitation enviada) y 204 (ya era colaborador).
     */
    private function api_put(string $url, array $payload): void {
        $curl = new \curl(['ignoresecurity' => true]);
        $curl->setHeader($this->build_headers([
            'Accept: application/vnd.github.v3+json',
            'Content-Type: application/json',
        ]));

        // Moodle curl no tiene método put nativo; se simula con setopt
        $curl->setopt('CURLOPT_CUSTOMREQUEST', 'PUT');
        $raw       = $curl->post($url, json_encode($payload));
        $http_code = $curl->get_info()['http_code'] ?? 0;

        if ($curl->get_errno()) {
            throw new \Exception('cURL error (PUT): ' . $curl->error);
        }

        // 201 = invitation enviada, 204 = ya era colaborador — ambos son éxito
        if (in_array($http_code, [201, 204], true)) {
            return;
        }

        $data = json_decode($raw, true);
        $msg  = $data['message'] ?? "HTTP {$http_code}";
        throw new \Exception('GitHub API (PUT): ' . $msg);
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
