<?php
// -----------------------------------------------------------------------------
// cli/setup_obsidian.php
//
// Script CLI para automatizar la configuración y primera sincronización
// del vault de Obsidian durante la instalación del plugin.
// -----------------------------------------------------------------------------

define('CLI_SCRIPT', true);

require_once(__DIR__ . '/../../../config.php');
require_once($CFG->libdir . '/filelib.php');
require_once($CFG->libdir . '/clilib.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/git_provider_interface.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/github_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/gitlab_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/obsidian_exporter.php');

echo "=== 1. Configurando los parámetros de integración con Obsidian ===\n";
set_config('obsidian_enabled', 1, 'block_gitmetrics');
set_config('obsidian_vault_path', '/obsidian-vault', 'block_gitmetrics');
set_config('obsidian_vault_name', 'OKF-Vault', 'block_gitmetrics');
echo "Integración habilitada (obsidian_enabled = 1, ruta = /obsidian-vault).\n";

$vault_path = '/obsidian-vault';
if (!is_dir($vault_path)) {
    echo "Creando directorio del vault en {$vault_path}...\n";
    if (!mkdir($vault_path, 0755, true)) {
        echo "[ERROR] No se pudo crear la carpeta del vault: {$vault_path}\n";
        exit(1);
    }
}
if (!is_writable($vault_path)) {
    echo "[WARNING] Sin permisos de escritura en {$vault_path}. Intentando ajustar o continuar...\n";
}

echo "=== 2. Realizando primera sincronización de documentos al vault ===\n";
$repourl    = get_config('block_gitmetrics', 'repo_url') ?: 'https://gitlab.com/julia8873/BdC';
$branch     = get_config('block_gitmetrics', 'default_branch') ?: 'main';
$provider   = get_config('block_gitmetrics', 'default_provider') ?: 'gitlab';
$gitlab_url = get_config('block_gitmetrics', 'gitlab_url') ?: 'https://gitlab.com';

if ($provider === 'github') {
    $token  = get_config('block_gitmetrics', 'github_token') ?: '';
    $client = new \block_gitmetrics\github_client($token);
} else {
    $token  = get_config('block_gitmetrics', 'gitlab_token') ?: '';
    $client = new \block_gitmetrics\gitlab_client($gitlab_url, $token);
}

try {
    $exporter = new \block_gitmetrics\obsidian_exporter($client, $repourl, $vault_path, $branch);
    $stats    = $exporter->export();

    echo "Sincronización con Obsidian completada exitosamente:\n";
    echo "   · Archivos escritos/actualizados: {$stats['written']}\n";
    echo "   · Archivos sin cambios (omitidos): {$stats['skipped']}\n";

    if (!empty($stats['errors'])) {
        echo "Aviso - errores menores durante la sincronización:\n";
        foreach ($stats['errors'] as $err) {
            echo "   {$err}\n";
        }
    }
} catch (\Throwable $e) {
    echo "[ERROR en sincronización Obsidian] " . $e->getMessage() . "\n";
    echo "La instalación de Moodle ha finalizado, pero la sincronización inicial reportó un error.\n";
}
