<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

/*
--8<-- [start:class_desc]
Calculadora de métricas de la Base de Conocimiento.

Orquesta la descarga del árbol del repositorio GitHub, el parseo
de cada archivo Markdown y el cálculo de las cuatro categorías
de métricas: Volumen, Red, Etiquetas y Formato.
--8<-- [end:class_desc]
*/
class metrics_calculator {

    /** @var git_provider_interface Cliente activo (GitHub o GitLab) */
    private git_provider_interface $client;
    private markdown_parser $parser;
    private string $token;
    private string $provider;
    private string $gitlab_url;

    /**
     * @param string $token    Token del proveedor (GitHub PAT o GitLab PRIVATE-TOKEN).
     * @param string $provider 'github' | 'gitlab' | 'auto'
     * @param string $gitlab_url URL base del servidor GitLab (solo para proveedor gitlab).
     *                           Ej: 'https://gitlab.osl.ugr.es' o 'http://localhost:8929'
     */
    // --8<-- [start:construct]
    public function __construct(string $token = '', string $provider = 'auto', string $gitlab_url = 'https://gitlab.com') {
        $this->token      = $token;
        $this->provider   = $provider;
        $this->gitlab_url = $gitlab_url;
        $this->client     = self::make_client($provider, $token, $gitlab_url);
        $this->parser     = new markdown_parser();
    }
    // --8<-- [end:construct]

    /**
     * Factoria de clientes: devuelve el cliente correcto segun el proveedor.
     * Tambien acepta una URL de repositorio para auto-detectar el proveedor.
     *
     * @param string $provider   'github', 'gitlab', o 'auto' (detecta por URL)
     * @param string $token      Token de autenticacion
     * @param string $gitlab_url URL base del servidor GitLab
     * @param string $repo_url   URL del repositorio (necesario solo para 'auto')
     */
    // --8<-- [start:make_client]
    public static function make_client(
        string $provider,
        string $token,
        string $gitlab_url = 'https://gitlab.com',
        string $repo_url = ''
    ): git_provider_interface {
        // Auto-deteccion por URL si el proveedor es 'auto'
        if ($provider === 'auto' && !empty($repo_url)) {
            if (strpos($repo_url, 'github.com') !== false) {
                $provider = 'github';
            } else {
                $provider = 'gitlab';
                // Extraer la URL base del servidor desde la URL del repo
                $parts = parse_url($repo_url);
                if (!empty($parts['host'])) {
                    $gitlab_url = ($parts['scheme'] ?? 'https') . '://' . $parts['host'];
                    if (!empty($parts['port'])) {
                        $gitlab_url .= ':' . $parts['port'];
                    }
                }
            }
        }

        if ($provider === 'gitlab') {
            return new gitlab_client($gitlab_url, $token);
        }
        return new github_client($token);
    }
    // --8<-- [end:make_client]

    // ---------------------------------------------------------------------
    // API pública
    // ---------------------------------------------------------------------

    /**
     * Punto de entrada principal.
     *
     * @param  string $repo_url URL pública del repositorio GitHub
     * @param  string $branch   Rama a analizar
     * @return array  Todas las métricas agrupadas por categoría
     */
    // --8<-- [start:calculate]
    public function calculate(string $repo_url, string $branch = 'main'): array {
        // Asegurar detección del proveedor según la URL al ejecutar el cálculo
        if ($this->provider === 'auto' || str_contains($repo_url, 'gitlab') || str_contains($repo_url, 'github.com')) {
            $this->client = self::make_client('auto', $this->token, $this->gitlab_url, $repo_url);
        }

        [$owner, $repo] = $this->parse_repo_url($repo_url);

        // Intentar con la rama solicitada; si no existe, probar la alternativa
        $actual_branch = $branch;
        try {
            $tree = $this->client->get_tree($owner, $repo, $branch);
        } catch (\Exception $e) {
            $fallback = ($branch === 'main') ? 'master' : 'main';
            try {
                $tree          = $this->client->get_tree($owner, $repo, $fallback);
                $actual_branch = $fallback;
            } catch (\Exception $e2) {
                throw new \Exception(
                    get_string('error_repo', 'block_gitmetrics') . ': ' . $e->getMessage()
                );
            }
        }

        // Separar ficheros y directorios
        $all_blobs  = array_values(array_filter($tree, fn($n) => $n['type'] === 'blob'));
        $all_trees  = array_values(array_filter($tree, fn($n) => $n['type'] === 'tree'));
        $md_blobs   = array_values(array_filter(
            $all_blobs,
            fn($n) => strtolower(pathinfo($n['path'], PATHINFO_EXTENSION)) === 'md'
        ));

        // Descargar y parsear cada archivo .md
        $files_data = $this->fetch_and_parse($owner, $repo, $actual_branch, $md_blobs);

        return [
            'repo_url'     => $repo_url,
            'owner'        => $owner,
            'repo'         => $repo,
            'branch'       => $actual_branch,
            'timestamp'    => time(),
            'volume'       => $this->calc_volume($files_data, $all_blobs, $all_trees, $tree),
            'network'      => $this->calc_network($files_data),
            'tags'         => $this->calc_tags($files_data),
            'format'       => $this->calc_format($files_data),
        ];
    }
    // --8<-- [end:calculate]

    // ---------------------------------------------------------------------
    // Paso previo: descargar y parsear archivos
    // ---------------------------------------------------------------------

    // --8<-- [start:fetch_and_parse]
    private function fetch_and_parse(
        string $owner,
        string $repo,
        string $branch,
        array  $md_blobs
    ): array {
        $files_data = [];
        foreach ($md_blobs as $blob) {
            $content    = $this->client->get_file_content($owner, $repo, $blob['path'], $branch);
            $parsed     = $this->parser->parse($content, $blob['path']);
            // El tamaño lo tomamos del API (más fiable que strlen en UTF-8)
            $parsed['size_bytes'] = $blob['size'] ?? strlen($content);
            $files_data[] = $parsed;
        }
        return $files_data;
    }
    // --8<-- [end:fetch_and_parse]

    // ---------------------------------------------------------------------
    // 1. Volumen y estructura
    // ---------------------------------------------------------------------

    // --8<-- [start:calc_volume]
    private function calc_volume(
        array $files_data,
        array $all_blobs,
        array $all_trees,
        array $full_tree
    ): array {
        $md_count    = count($files_data);
        $total_blobs = count($all_blobs);

        $sizes       = array_column($files_data, 'size_bytes');
        $word_counts = array_column($files_data, 'word_count');

        // Profundidad: número de '/' en la ruta de cada nodo
        $all_paths = array_column($full_tree, 'path');
        $depths    = array_map(fn($p) => substr_count($p, '/'), $all_paths);

        // Archivos esenciales OKF (búsqueda case-insensitive en todo el árbol)
        $all_paths_lower = array_map('strtolower', $all_paths);
        $essential_keys  = ['AGENTS.md', 'LOG.md', 'INDEX.md'];
        $essential       = [];
        foreach ($essential_keys as $ek) {
            $ek_lower = strtolower($ek);
            // Buscar en cualquier nivel del árbol
            $found = array_filter($all_paths_lower, fn($p) => $p === $ek_lower || str_ends_with($p, '/' . $ek_lower));
            $essential[$ek] = !empty($found)
                ? ['present' => true, 'path' => array_values($found)[0]]
                : ['present' => false, 'path' => null];
        }

        // Distribución de archivos .md por directorio
        $files_by_dir = [];
        foreach ($files_data as $f) {
            $dir = dirname($f['path']);
            $dir = ($dir === '.') ? '/' : $dir;
            if (!isset($files_by_dir[$dir])) $files_by_dir[$dir] = 0;
            $files_by_dir[$dir]++;
        }
        arsort($files_by_dir);

        // Detalle por archivo
        $files_detail = array_map(fn($f) => [
            'path'       => $f['path'],
            'size_bytes' => $f['size_bytes'],
            'word_count' => $f['word_count'],
        ], $files_data);

        return [
            'md_file_count'    => $md_count,
            'total_file_count' => $total_blobs,
            'dir_count'        => count($all_trees),
            'total_size_bytes' => array_sum($sizes),
            'avg_size_bytes'   => $md_count > 0 ? round(array_sum($sizes) / $md_count, 2) : 0,
            'total_words'      => array_sum($word_counts),
            'avg_word_count'   => $md_count > 0 ? round(array_sum($word_counts) / $md_count, 2) : 0,
            'max_word_count'   => !empty($word_counts) ? max($word_counts) : 0,
            'min_word_count'   => !empty($word_counts) ? min($word_counts) : 0,
            'max_depth'        => !empty($depths) ? max($depths) : 0,
            'avg_depth'        => !empty($depths) ? round(array_sum($depths) / count($depths), 2) : 0,
            'essential_files'  => $essential,
            'files_by_dir'     => $files_by_dir,
            'files_detail'     => $files_detail,
        ];
    }
    // --8<-- [end:calc_volume]

    // ---------------------------------------------------------------------
    // 2. Red y conectividad
    // ---------------------------------------------------------------------

    // --8<-- [start:calc_network]
    private function calc_network(array $files_data): array {
        $n = count($files_data);

        if ($n === 0) {
            return [
                'total_nodes'          => 0,
                'avg_connections'      => 0.0,
                'orphan_count'         => 0,
                'orphan_rate'          => 0.0,
                'total_internal_links' => 0,
                'link_density'         => 0.0,
                'connectivity_detail'  => [],
            ];
        }

        $file_paths = array_column($files_data, 'path');
        $total_words = array_sum(array_column($files_data, 'word_count'));

        // outgoing[i] = número de enlaces VÁLIDOS que salen del nodo i
        $outgoing    = array_fill(0, $n, 0);
        // has_incoming[i] = true si algún otro nodo enlaza al nodo i
        $has_incoming = array_fill(0, $n, false);
        $total_links  = 0;

        foreach ($files_data as $i => $file) {
            foreach ($file['internal_links'] as $link_raw) {
                // Normalizar: quitar anclas (#) y parámetros (?)
                $link = strtolower(preg_replace('/[?#].*$/', '', $link_raw));
                $link = trim($link, './');

                // Intentar resolver contra cada nodo conocido
                foreach ($file_paths as $j => $known_path) {
                    if ($j === $i) continue;
                    $known_lower = strtolower($known_path);
                    $known_base  = strtolower(basename($known_path));

                    if (
                        $link === $known_lower ||
                        $link === $known_base  ||
                        str_ends_with($known_lower, '/' . $link)
                    ) {
                        $outgoing[$i]++;
                        $has_incoming[$j] = true;
                        $total_links++;
                        break;
                    }
                }
            }
        }

        // Nodos huérfanos: sin enlaces salientes Y sin enlaces entrantes
        $orphan_indices = [];
        for ($i = 0; $i < $n; $i++) {
            if ($outgoing[$i] === 0 && !$has_incoming[$i]) {
                $orphan_indices[] = $i;
            }
        }

        $orphan_count    = count($orphan_indices);
        $avg_connections = round(array_sum($outgoing) / $n, 4);
        $orphan_rate     = round(($orphan_count / $n) * 100, 2);
        $link_density    = $total_words > 0 ? round($total_links / $total_words, 6) : 0.0;

        // Detalle por nodo
        $detail = [];
        for ($i = 0; $i < $n; $i++) {
            $detail[] = [
                'path'         => $files_data[$i]['path'],
                'outgoing'     => $outgoing[$i],
                'has_incoming' => $has_incoming[$i],
                'is_orphan'    => in_array($i, $orphan_indices),
            ];
        }

        return [
            'total_nodes'          => $n,
            'avg_connections'      => $avg_connections,
            'orphan_count'         => $orphan_count,
            'orphan_rate'          => $orphan_rate,
            'total_internal_links' => $total_links,
            'link_density'         => $link_density,
            'connectivity_detail'  => $detail,
        ];
    }
    // --8<-- [end:calc_network]

    // ---------------------------------------------------------------------
    // 3. Etiquetas (tags)
    // ---------------------------------------------------------------------

    // --8<-- [start:calc_tags]
    private function calc_tags(array $files_data): array {
        $tag_frequency = [];  // tag => número de archivos que lo usan
        $tag_sets      = [];  // [ [tags del archivo 0], [tags del archivo 1], ... ]

        foreach ($files_data as $file) {
            $tags = array_map('strtolower', array_map('trim', $file['tags'] ?? []));
            $tags = array_values(array_filter($tags));
            $tag_sets[] = $tags;

            foreach ($tags as $tag) {
                if (!isset($tag_frequency[$tag])) $tag_frequency[$tag] = 0;
                $tag_frequency[$tag]++;
            }
        }

        $unique_tags        = array_keys($tag_frequency);
        $total_unique       = count($unique_tags);
        $total_usage        = array_sum($tag_frequency);
        $files_with_tags    = count(array_filter($tag_sets, fn($ts) => !empty($ts)));
        $files_without_tags = count($files_data) - $files_with_tags;

        // Distancia de Hamming media entre pares de documentos
        $hamming_avg = $this->hamming_avg_distance($tag_sets, $unique_tags);

        // Top 10 etiquetas más usadas
        arsort($tag_frequency);
        $top_tags = array_slice($tag_frequency, 0, 10, true);

        return [
            'total_unique_tags'  => $total_unique,
            'total_tag_usage'    => $total_usage,
            'files_with_tags'    => $files_with_tags,
            'files_without_tags' => $files_without_tags,
            'hamming_avg'        => round($hamming_avg, 4),
            'top_tags'           => $top_tags,
            'all_tags'           => $tag_frequency,
        ];
    }
    // --8<-- [end:calc_tags]

    /**
     * Distancia de Hamming media entre todos los pares de documentos.
     *
     * Cada documento se representa como un vector binario de longitud = |tags únicos|,
     * donde la posición k vale 1 si el documento tiene el tag k.
     *
     * Hamming(A, B) = número de posiciones donde A y B difieren.
     * Se devuelve la media sobre todos los pares (i, j) con i < j.
     *
     * Un valor alto indica que los documentos tienen conjuntos de tags
     * muy distintos entre sí (diversidad de etiquetado).
     */
    private function hamming_avg_distance(array $tag_sets, array $unique_tags): float {
        $n = count($tag_sets);
        if ($n < 2 || empty($unique_tags)) {
            return 0.0;
        }

        // Construir vectores binarios
        $vectors = [];
        foreach ($tag_sets as $tags) {
            $vec = [];
            foreach ($unique_tags as $tag) {
                $vec[] = in_array($tag, $tags, true) ? 1 : 0;
            }
            $vectors[] = $vec;
        }

        $tag_count     = count($unique_tags);
        $total_distance = 0;
        $pairs          = 0;

        for ($i = 0; $i < $n; $i++) {
            for ($j = $i + 1; $j < $n; $j++) {
                $dist = 0;
                for ($k = 0; $k < $tag_count; $k++) {
                    if ($vectors[$i][$k] !== $vectors[$j][$k]) {
                        $dist++;
                    }
                }
                $total_distance += $dist;
                $pairs++;
            }
        }

        return $pairs > 0 ? ($total_distance / $pairs) : 0.0;
    }

    // ---------------------------------------------------------------------
    // 4. Validación de formato
    // ---------------------------------------------------------------------

    // --8<-- [start:calc_format]
    private function calc_format(array $files_data): array {
        $total = count($files_data);

        if ($total === 0) {
            return [
                'files_with_frontmatter'  => 0,
                'frontmatter_rate'        => 0.0,
                'valid_frontmatter_count' => 0,
                'valid_frontmatter_rate'  => 0.0,
                'valid_markdown_count'    => 0,
                'valid_markdown_rate'     => 0.0,
                'frontmatter_errors'      => [],
                'markdown_errors'         => [],
            ];
        }

        $with_fm    = array_filter($files_data, fn($f) => $f['has_frontmatter']);
        $valid_fm   = array_filter($files_data, fn($f) => $f['is_valid_frontmatter']);
        $valid_md   = array_filter($files_data, fn($f) => $f['is_valid_markdown']);

        // Recopilar errores por archivo
        $fm_errors = [];
        $md_errors = [];
        foreach ($files_data as $f) {
            if (!empty($f['frontmatter_errors'])) {
                $fm_errors[$f['path']] = $f['frontmatter_errors'];
            }
            if (!empty($f['markdown_errors'])) {
                $md_errors[$f['path']] = $f['markdown_errors'];
            }
        }

        return [
            'files_with_frontmatter'  => count($with_fm),
            'frontmatter_rate'        => round((count($with_fm) / $total) * 100, 2),
            'valid_frontmatter_count' => count($valid_fm),
            'valid_frontmatter_rate'  => round((count($valid_fm) / $total) * 100, 2),
            'valid_markdown_count'    => count($valid_md),
            'valid_markdown_rate'     => round((count($valid_md) / $total) * 100, 2),
            'frontmatter_errors'      => $fm_errors,
            'markdown_errors'         => $md_errors,
        ];
    }
    // --8<-- [end:calc_format]

    // ---------------------------------------------------------------------
    // Utilidades
    // ---------------------------------------------------------------------

    /**
     * Extrae [owner, repo] de una URL de GitHub.
     * Acepta: https://github.com/owner/repo
     *         https://github.com/owner/repo.git
     *         https://github.com/owner/repo/
     */
    /**
     * Extrae owner y nombre del repo de cualquier URL Git (GitHub o GitLab).
     *
     * Formatos soportados:
     *   - https://github.com/owner/repo
     *   - https://github.com/owner/repo.git
     *   - https://gitlab.com/owner/repo
     *   - https://gitlab.osl.ugr.es/grupo/subgrupo/repo  (namespaces anidados de GitLab)
     *   - http://localhost:8929/owner/repo
     */
    // --8<-- [start:parse_repo_url]
    private function parse_repo_url(string $url): array {
        $url = rtrim(trim($url), '/');
        $url = preg_replace('/\.git$/i', '', $url);

        // GitHub: host fijo
        if (preg_match('#^https?://github\.com/([^/]+)/([^/]+)$#i', $url, $m)) {
            return [$m[1], $m[2]];
        }

        // GitLab: cualquier host, owner puede tener namespaces (grupo/subgrupo)
        // Capturamos todo lo anterior al ultimo segmento como owner y el ultimo como repo
        if (preg_match('#^https?://[^/]+/(.+)/([^/]+)$#i', $url, $m)) {
            return [$m[1], $m[2]];
        }

        throw new \Exception(get_string('error_invalid_url', 'block_gitmetrics'));
    }
    // --8<-- [end:parse_repo_url]
}
