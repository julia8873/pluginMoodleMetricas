<?php
// -----------------------------------------------------------------------------
// Script CLI para sincronización unificada de Moodle, Bloques y Obsidian
// al configurar un repositorio Git (GitLab o GitHub) y un Token.
// -----------------------------------------------------------------------------

define('CLI_SCRIPT', true);

require_once(__DIR__ . '/../../../config.php');
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/git_provider_interface.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/github_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/gitlab_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/obsidian_exporter.php');

global $DB;

// Obtener argumentos CLI
$longparams = ['url:', 'token:', 'branch:', 'help'];
$shortparams = ['u:', 't:', 'b:', 'h'];
$options = getopt(implode('', $shortparams), $longparams);

if (isset($options['h']) || isset($options['help']) || (empty($options['url']) && empty($options['u']))) {
    echo "Uso: php setup_git.php --url=\"https://gitlab.com/owner/repo\" --token=\"glpat-xxxx\" [--branch=\"main\"]\n";
    exit(0);
}

$url = $options['url'] ?? $options['u'] ?? '';
$token = $options['token'] ?? $options['t'] ?? '';
$branch = $options['branch'] ?? $options['b'] ?? 'main';

$url = rtrim(trim($url), '/');
$token = trim($token);
$branch = trim($branch);

// Determinar proveedor y componentes
$provider = 'github';
$gitlab_url = 'https://gitlab.com';
$owner = '';
$repo = '';

if (preg_match('#^https?://([^/]+)/([^/]+)/([^/.]+)(?:\.git)?$#i', $url, $matches)) {
    $domain = $matches[1];
    $owner = $matches[2];
    $repo = $matches[3];
    
    if (stripos($domain, 'gitlab') !== false || stripos($domain, 'osl.ugr.es') !== false || stripos($url, 'gitlab') !== false) {
        $provider = 'gitlab';
        $parts = parse_url($url);
        $gitlab_url = ($parts['scheme'] ?? 'https') . '://' . ($parts['host'] ?? 'gitlab.com') . (!empty($parts['port']) ? ':' . $parts['port'] : '');
    } else {
        $provider = 'github';
    }
} else {
    echo "Error: URL de repositorio no válida ($url). Debe ser del tipo https://gitlab.com/usuario/repositorio\n";
    exit(1);
}

echo "===============================================================\n";
echo " Sincronizando Moodle & Obsidian con $provider\n";
echo " Repositorio: $owner/$repo ($url) - Rama: $branch\n";
echo "===============================================================\n";

// 1. Actualizar configuración global en la tabla config_plugins
set_config('default_provider', $provider, 'block_gitmetrics');
set_config('default_branch', $branch, 'block_gitmetrics');

if ($provider === 'gitlab') {
    set_config('gitlab_url', $gitlab_url, 'block_gitmetrics');
    if ($token !== '') {
        set_config('gitlab_token', $token, 'block_gitmetrics');
    }
    echo "[OK] Ajustes globales actualizados para GitLab ($gitlab_url).\n";
} else {
    if ($token !== '') {
        set_config('github_token', $token, 'block_gitmetrics');
    }
    echo "[OK] Ajustes globales actualizados para GitHub.\n";
}

// 2. Configurar e inicializar Obsidian en Moodle
set_config('obsidian_enabled', 1, 'block_gitmetrics');
set_config('obsidian_vault_path', '/obsidian-vault', 'block_gitmetrics');
set_config('obsidian_vault_name', 'OKF-Vault', 'block_gitmetrics');
echo "[OK] Integración con Obsidian habilitada (Ruta: /obsidian-vault).\n";

// 3. Actualizar todas las instancias del bloque en las asignaturas
$instances = $DB->get_records('block_instances', ['blockname' => 'gitmetrics']);
$updated_count = 0;

foreach ($instances as $instance) {
    $config = new stdClass();
    if (!empty($instance->configdata)) {
        $decoded = @unserialize(base64_decode($instance->configdata));
        if (is_object($decoded)) {
            $config = $decoded;
        }
    }
    
    $config->repo_url = $url;
    $config->provider = $provider;
    $config->branch = $branch;
    
    $instance->configdata = base64_encode(serialize($config));
    $instance->timemodified = time();
    $DB->update_record('block_instances', $instance);
    $updated_count++;
}

echo "[OK] $updated_count instancias de bloque actualizadas con la nueva URL.\n";

// 4. Purgar cachés de Moodle y de métricas
$DB->delete_records('block_gitmetrics_cache');
purge_all_caches();
echo "[OK] Caché de Moodle y de métricas limpiada.\n";

// 5. Disparar sincronización inicial hacia la carpeta del vault de Obsidian
echo "[i] Sincronizando archivos .md con el vault de Obsidian...\n";
try {
    if ($provider === 'github') {
        $client = new \block_gitmetrics\github_client($token);
    } else {
        $client = new \block_gitmetrics\gitlab_client($gitlab_url, $token);
    }
    
    $exporter = new \block_gitmetrics\obsidian_exporter($client, $url, '/obsidian-vault', $branch);
    $stats = $exporter->export();
    
    echo "[OK] Exportación a Obsidian completada:\n";
    echo "     · Archivos exportados/actualizados: {$stats['written']}\n";
    echo "     · Archivos sin cambios (omitidos): {$stats['skipped']}\n";
    if (!empty($stats['errors'])) {
        foreach ($stats['errors'] as $err) {
            echo "     [!] Aviso: {$err}\n";
        }
    }
} catch (Exception $exc) {
    echo "[!] No se pudo exportar a Obsidian en este momento: " . $exc->getMessage() . "\n";
}

echo "===============================================================\n";
echo " Sincronización de Moodle y Obsidian finalizada con éxito.\n";
echo "===============================================================\n";
