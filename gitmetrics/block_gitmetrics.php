<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Bloque principal: block_gitmetrics
 *
 * Analiza un repositorio GitHub público (o privado con token) con
 * estructura OKF y muestra las métricas cuantitativas de la Base
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

    // ── Contenido del bloque ──────────────────────────────────────────────

    public function get_content() {
        global $DB, $PAGE;

        if ($this->content !== null) {
            return $this->content;
        }

        $this->content         = new stdClass();
        $this->content->footer = '';

        $renderer = $this->page->get_renderer('block_gitmetrics');

        // ── 1. Obtener URL del repo desde la configuración de instancia ──
        $repourl = !empty($this->config->github_url)
            ? trim($this->config->github_url)
            : '';

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
                // ── 4. Calcular métricas ──────────────────────────────────
                $token      = get_config('block_gitmetrics', 'github_token') ?: '';
                $calculator = new \block_gitmetrics\metrics_calculator($token);
                $metrics    = $calculator->calculate($repourl, $branch);

                $ttl = (int)(get_config('block_gitmetrics', 'cache_ttl') ?: 3600);
                $cache->set($repourl, $this->instance->id, $metrics);
            }

            // ── 5. Renderizar ─────────────────────────────────────────────
            $this->content->text = $renderer->render_metrics($metrics);

        } catch (\Exception $e) {
            $this->content->text = $renderer->render_error($e->getMessage());
        }

        return $this->content;
    }
}
