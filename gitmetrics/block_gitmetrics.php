<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Bloque principal: block_gitmetrics
 *
 * Analiza un repositorio GitHub o GitLab (OSL / local / cloud) con
 * estructura OKF y muestra las metricas cuantitativas de la Base
 * de Conocimiento en el bloque de Moodle.
 */
class block_gitmetrics extends block_base {

    // ── Inicialización ────────────────────────────────────────────────────

    public function init() {
        $this->title = get_string('pluginname', 'block_gitmetrics');
    }

    public function has_config() {
        return true;
    }

    // El bloque se puede añadir varias veces en la misma página
    public function instance_allow_multiple() {
        return true;
    }

    public function instance_create() {
        if (!empty($this->page->course->id) && $this->page->course->id > 1) {
            if (class_exists('\block_gitmetrics\matrix_helper')) {
                \block_gitmetrics\matrix_helper::ensure_room_and_bot((int)$this->page->course->id);
            }
        }
        return parent::instance_create();
    }

    public function instance_config_save($data, $nolongerused = false) {
        if (!empty($this->page->course->id) && $this->page->course->id > 1) {
            if (class_exists('\block_gitmetrics\matrix_helper')) {
                \block_gitmetrics\matrix_helper::ensure_room_and_bot((int)$this->page->course->id);
            }
        }
        return parent::instance_config_save($data, $nolongerused);
    }

    // ── Contenido del bloque ──────────────────────────────────────────────

    public function get_content() {
        global $DB, $PAGE;

        if ($this->content !== null) {
            return $this->content;
        }

        $this->content         = new stdClass();
        $this->content->footer = '';

        $renderer = $this->page->get_renderer('block_gitmetrics');

        // ── 1. Obtener URL del repo y proveedor desde la config de instancia ──
        // Nuevo campo unificado: config_repo_url
        // Retrocompatibilidad con el antiguo campo config_github_url
        $repourl  = !empty($this->config->repo_url)
            ? trim($this->config->repo_url)
            : (!empty($this->config->github_url) ? trim($this->config->github_url) : '');

        $provider = !empty($this->config->provider)
            ? trim($this->config->provider)
            : (get_config('block_gitmetrics', 'default_provider') ?: 'github');

        if (empty($repourl)) {
            $this->content->text = $renderer->render_no_repo();
            return $this->content;
        }

        // ── 2. Rama (instancia → global → 'main') ───────────────────────
        $branch = !empty($this->config->branch)
            ? trim($this->config->branch)
            : (get_config('block_gitmetrics', 'default_branch') ?: 'main');

        try {
            // ── 3. Caché ─────────────────────────────────────────────────
            $cache = new \block_gitmetrics\metrics_cache($DB);

            // Forzar refresco si el usuario lo ha marcado en la config
            $force_refresh = !empty($this->config->force_refresh);
            if ($force_refresh) {
                $cache->invalidate($this->instance->id);
                // Resetear el flag para que no refuerce en cada carga
                $this->config->force_refresh = 0;
                $this->instance_config_save($this->config);
            }

            $metrics = $cache->get($repourl, $this->instance->id);

            if ($metrics === null) {
                // ── 4. Calcular metricas ──────────────────────────────────
                if (str_contains($repourl, 'github.com')) {
                    $token      = get_config('block_gitmetrics', 'github_token') ?: '';
                    $gitlab_url = 'https://gitlab.com';
                    $provider   = 'github';
                } elseif ($provider === 'gitlab' || str_contains($repourl, 'gitlab')) {
                    $token      = get_config('block_gitmetrics', 'gitlab_token') ?: '';
                    $gitlab_url = get_config('block_gitmetrics', 'gitlab_url') ?: 'https://gitlab.com';
                    $provider   = 'gitlab';
                } else {
                    $token      = get_config('block_gitmetrics', 'github_token') ?: '';
                    $gitlab_url = 'https://gitlab.com';
                }
                $calculator = new \block_gitmetrics\metrics_calculator($token, $provider, $gitlab_url);
                $metrics    = $calculator->calculate($repourl, $branch);

                $cache->set($repourl, $this->instance->id, $metrics);
            }

            // ------------------------------------------------------------------
            // 5. Renderizar
            // ------------------------------------------------------------------
            $courseid = isset($this->page->course->id) ? (int)$this->page->course->id : 1;
            $blockid  = isset($this->instance->id) ? (int)$this->instance->id : 0;
            $this->content->text = $renderer->render_metrics($metrics, $courseid, $blockid);

        } catch (\Throwable $e) {
            $this->content->text = $renderer->render_error($e->getMessage());
        }

        return $this->content;
    }
}
