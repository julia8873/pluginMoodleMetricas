<?php
// ─────────────────────────────────────────────────────────────────────────────
// cli/export_obsidian.php
//
// Script CLI OPCIONAL para sincronizar el repositorio Git con un vault de Obsidian.
//
// Uso:
//   docker exec --user daemon moodle-app \
//     php /bitnami/moodle/blocks/gitmetrics/cli/export_obsidian.php
//
//   Con parámetros opcionales:
//     --vault=/ruta/al/vault   Sobreescribe la ruta configurada en los ajustes del plugin.
//     --dry-run                Muestra qué archivos se escribirían sin escribir nada.
//
// Para ELIMINAR la integración con Obsidian, borra simplemente este archivo
// y classes/obsidian_exporter.php. No hay dependencias en otros ficheros del plugin
// salvo los bloques marcados con "OBSIDIAN_OPTIONAL" en settings.php y
// cli/setup_course.php.
// ─────────────────────────────────────────────────────────────────────────────

define('CLI_SCRIPT', true);

require_once(__DIR__ . '/../../../config.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/git_provider_interface.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/github_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/gitlab_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/obsidian_exporter.php');

// ── Parámetros CLI ────────────────────────────────────────────────────────────
$options = getopt('', ['vault:', 'dry-run', 'help']);

if (isset($options['help'])) {
    echo <<<HELP
Sincroniza el repositorio Git configurado en block_gitmetrics con un vault de Obsidian local.

Opciones:
  --vault=/ruta    Sobreescribe la ruta del vault configurada en Administración del sitio.
  --dry-run        Muestra los archivos que se escribirían sin modificar el disco.
  --help           Muestra este mensaje de ayuda.

Ejemplo:
  php cli/export_obsidian.php --vault=/home/julia/Documents/OKF-Vault

HELP;
    exit(0);
}

// ── Leer configuración del plugin ─────────────────────────────────────────────
// Leer si la integración con Obsidian está habilitada en los ajustes del plugin
$obsidian_enabled = (bool) get_config('block_gitmetrics', 'obsidian_enabled');
if (!$obsidian_enabled && !isset($options['vault'])) {
    echo "[WARNING] La integración con Obsidian está desactivada en los ajustes del plugin.\n";
    echo "          Actívala en Administración del sitio > Plugins > Bloques > Git Knowledge Base Metrics\n";
    echo "          o usa --vault=/ruta para forzar la exportación sin cambiar los ajustes.\n";
    exit(1);
}

// Ruta del vault: parámetro CLI tiene prioridad sobre los ajustes del plugin
$vault_path = $options['vault'] ?? get_config('block_gitmetrics', 'obsidian_vault_path');
if (empty($vault_path)) {
    echo "[ERROR] No se ha configurado la ruta del vault de Obsidian.\n";
    echo "        Configúrala en Administración del sitio > Plugins > Bloques > Git Knowledge Base Metrics\n";
    echo "        o usa --vault=/ruta para especificarla directamente.\n";
    exit(2);
}

// Validar que el directorio del vault existe y tiene permisos de escritura
if (!is_dir($vault_path)) {
    echo "[INFO] La carpeta del vault no existe, intentando crearla: {$vault_path}\n";
    if (!mkdir($vault_path, 0755, true)) {
        echo "[ERROR] No se pudo crear la carpeta del vault: {$vault_path}\n";
        exit(3);
    }
}
if (!is_writable($vault_path)) {
    echo "[ERROR] Sin permisos de escritura en el vault: {$vault_path}\n";
    exit(4);
}

// ── Configuración del repositorio ─────────────────────────────────────────────
$repourl    = get_config('block_gitmetrics', 'repo_url') ?: 'https://gitlab.com/julia8873/BdC';
$branch     = get_config('block_gitmetrics', 'default_branch') ?: 'main';
$provider   = get_config('block_gitmetrics', 'default_provider') ?: 'gitlab';
$gitlab_url = get_config('block_gitmetrics', 'gitlab_url') ?: 'https://gitlab.com';

// Instanciar el cliente adecuado según el proveedor
if ($provider === 'github') {
    $token  = get_config('block_gitmetrics', 'github_token') ?: '';
    $client = new \block_gitmetrics\github_client($token);
} else {
    $token  = get_config('block_gitmetrics', 'gitlab_token') ?: '';
    $client = new \block_gitmetrics\gitlab_client($gitlab_url, $token);
}

// ── Dry-run mode ──────────────────────────────────────────────────────────────
$dry_run = isset($options['dry-run']);
if ($dry_run) {
    echo "[DRY-RUN] No se escribirá nada en disco. Solo se mostraría:\n";
    echo "  Vault:       {$vault_path}\n";
    echo "  Repositorio: {$repourl}\n";
    echo "  Rama:        {$branch}\n\n";
}

// ── Ejecutar exportación ──────────────────────────────────────────────────────
echo "=== Exportando repositorio a Obsidian ===\n";
echo "Repositorio: {$repourl} (rama: {$branch})\n";
echo "Vault:       {$vault_path}\n\n";

if (!$dry_run) {
    try {
        $exporter = new \block_gitmetrics\obsidian_exporter($client, $repourl, $vault_path, $branch);
        $stats    = $exporter->export();

        echo "Exportacion completada:\n";
        echo "   · Archivos escritos/actualizados: {$stats['written']}\n";
        echo "   · Archivos sin cambios (omitidos): {$stats['skipped']}\n";

        if (!empty($stats['errors'])) {
            echo "Errores durante la exportacion:\n";
            foreach ($stats['errors'] as $err) {
                echo "   {$err}\n";
            }
        }

    } catch (\Throwable $e) {
        echo "[ERROR FATAL] " . $e->getMessage() . "\n";
        exit(5);
    }
} else {
    echo "[DRY-RUN] Exportación simulada finalizada. Ejecuta sin --dry-run para escribir.\n";
}
