<?php
// -----------------------------------------------------------------------------
// classes/task/sync_obsidian.php (Módulo Obsidian)
//
// Tarea programada de Moodle (Scheduled Task) para sincronizar automáticamente
// el repositorio Git con el vault local de Obsidian cada hora mediante el
// sistema cron de Moodle.
//
// Para desactivar o eliminar este módulo: borra este archivo y su entrada
// en db/tasks.php.
// -----------------------------------------------------------------------------

namespace block_gitmetrics\task;

defined('MOODLE_INTERNAL') || die();

require_once($CFG->dirroot . '/blocks/gitmetrics/classes/obsidian_exporter.php');

class sync_obsidian extends \core\task\scheduled_task {

    /**
     * Devuelve el nombre humanamente legible de la tarea programada.
     */
    public function get_name(): string {
        return get_string('task_sync_obsidian', 'block_gitmetrics');
    }

    /**
     * Ejecuta la sincronizacion automatica con el vault.
     */
    public function execute(): void {
        global $CFG;

        // Verificar si la integracion con Obsidian esta activada en los ajustes del plugin
        $obsidian_enabled = (bool) get_config('block_gitmetrics', 'obsidian_enabled');
        if (!$obsidian_enabled) {
            mtrace('Sincronizacion Obsidian: desactivada en los ajustes del bloque.');
            return;
        }

        $vault_path = get_config('block_gitmetrics', 'obsidian_vault_path');
        if (empty($vault_path)) {
            mtrace('Sincronizacion Obsidian: ruta del vault no configurada.');
            return;
        }

        require_once($CFG->libdir . '/filelib.php');
        require_once($CFG->dirroot . '/blocks/gitmetrics/classes/git_provider_interface.php');
        require_once($CFG->dirroot . '/blocks/gitmetrics/classes/github_client.php');
        require_once($CFG->dirroot . '/blocks/gitmetrics/classes/gitlab_client.php');

        $provider = get_config('block_gitmetrics', 'default_provider') ?: 'gitlab';
        $repourl  = get_config('block_gitmetrics', 'repo_url') ?: 'https://gitlab.com/julia8873/BdC';
        $branch   = get_config('block_gitmetrics', 'default_branch') ?: 'main';

        if ($provider === 'github') {
            $token  = get_config('block_gitmetrics', 'github_token') ?: '';
            $client = new \block_gitmetrics\github_client($token);
        } else {
            $token      = get_config('block_gitmetrics', 'gitlab_token') ?: '';
            $gitlab_url = get_config('block_gitmetrics', 'gitlab_url') ?: 'https://gitlab.com';
            $client     = new \block_gitmetrics\gitlab_client($gitlab_url, $token);
        }

        mtrace("Iniciando sincronizacion programada hacia el vault: {$vault_path}");
        $exporter = new \block_gitmetrics\obsidian_exporter($client, $repourl, $vault_path, $branch);
        $stats    = $exporter->export();

        mtrace("Sincronizacion completada: {$stats['written']} escritos, {$stats['skipped']} sin cambios.");
        if (!empty($stats['errors'])) {
            mtrace("Errores en sincronizacion programada:");
            foreach ($stats['errors'] as $err) {
                mtrace("  - {$err}");
            }
        }
    }
}
