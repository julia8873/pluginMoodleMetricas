<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Renderer HTML para block_gitmetrics.
 *
 * Genera la interfaz visual completa del bloque: cuatro secciones con
 * tarjetas de métricas, indicadores de estado, tablas de detalle y
 * estilos inline para que funcione sin necesidad de un CSS externo.
 */
class block_gitmetrics_renderer extends plugin_renderer_base {

    // Contexto del repositorio (se establece en render_metrics / render_fullpage_metrics)
    private string $ctx_repo_url = '';
    private string $ctx_branch   = 'main';
    private string $ctx_provider = 'gitlab';
    private int    $ctx_courseid = 1;
    private int    $ctx_blockid  = 0;

    private function set_repo_context(array $m, int $courseid, int $blockid): void {
        $this->ctx_repo_url = $m['repo_url']  ?? '';
        $this->ctx_branch   = $m['branch']    ?? 'main';
        $this->ctx_provider = $m['provider']  ?? 'gitlab';
        $this->ctx_courseid = $courseid;
        $this->ctx_blockid  = $blockid;
    }

    /**
     * Genera la URL del visor de archivo en vivo (view_file.php) para una ruta dada.
     * Usa out() (ya devuelve &amp; HTML-safe). NO aplicar s() sobre este resultado:
     * moodle_url::out() ya está preparado para usarse directamente en atributos HTML.
     */
    private function file_viewer_url(string $filepath): string {
        return (new moodle_url('/blocks/gitmetrics/view_file.php', [
            'courseid' => $this->ctx_courseid,
            'blockid'  => $this->ctx_blockid,
            'path'     => $filepath,
            'repo_url' => $this->ctx_repo_url,
            'branch'   => $this->ctx_branch,
        ]))->out(); // out() ya devuelve &amp; — NO envolver con s()
    }

    /**
     * Genera la URL directa al archivo en el servidor Git externo (GitLab / GitHub).
     */
    private function file_external_url(string $filepath): string {
        $encoded = str_replace('%2F', '/', rawurlencode($filepath));
        if (str_contains($this->ctx_repo_url, 'github.com')) {
            return rtrim($this->ctx_repo_url, '/') . '/blob/' . rawurlencode($this->ctx_branch) . '/' . $encoded;
        }
        // GitLab
        return rtrim($this->ctx_repo_url, '/') . '/-/blob/' . rawurlencode($this->ctx_branch) . '/' . $encoded;
    }

    // -------------------------------------------------------------------------
    // Punto de entrada principal
    // -------------------------------------------------------------------------

    public function render_metrics(array $m, int $courseid = 1, int $blockid = 0): string {
        $this->set_repo_context($m, $courseid, $blockid);
        $html  = $this->styles();
        $html .= '<div class="gm-wrap">';
        $html .= $this->render_repo_header($m);

        if ($blockid > 0) {
            $fullpageurl = new moodle_url('/blocks/gitmetrics/view.php', ['courseid' => $courseid, 'blockid' => $blockid]);
            $html .= '<div style="margin: 10px 0; text-align: center;">';
            $html .= '<a href="' . $fullpageurl->out() . '" class="btn btn-primary btn-sm" style="width: 100%; font-weight: bold;">Ver en página completa &rarr;</a>';
            $html .= '</div>';
        }

        $html .= $this->render_volume($m['volume']);
        $html .= $this->render_network($m['network']);
        $html .= $this->render_tags($m['tags']);
        $html .= $this->render_format($m['format']);
        $html .= '<div class="gm-footer">'
               . get_string('last_updated', 'block_gitmetrics') . ': '
               . userdate($m['timestamp'])
               . '</div>';
        $html .= '</div>';
        return $html;
    }

    public function render_fullpage_metrics(array $m, int $courseid = 1, int $blockid = 0): string {
        $this->set_repo_context($m, $courseid, $blockid);
        $html  = $this->styles();
        $html .= '<div class="gm-wrap gm-fullpage" style="font-size: 1.05em;">';
        $html .= $this->render_repo_header($m);

        $html .= '<div class="gm-topics-container" style="display: flex; flex-direction: column; gap: 15px; margin-top: 18px;">';

        // Volumen
        $html .= '<details class="gm-topic-toggle" open>'
               . '<summary class="gm-topic-header">Volumen y Tamaño de la Base de Conocimiento</summary>'
               . '<div class="gm-topic-body">' . $this->render_volume($m['volume']) . '</div>'
               . '</details>';

        // Red
        $html .= '<details class="gm-topic-toggle" open>'
               . '<summary class="gm-topic-header">Red de Enlaces e Interconectividad Markdown</summary>'
               . '<div class="gm-topic-body">' . $this->render_network($m['network']) . '</div>'
               . '</details>';

        // Etiquetas
        $html .= '<details class="gm-topic-toggle" open>'
               . '<summary class="gm-topic-header">Taxonomía, Metadatos y Etiquetas YAML</summary>'
               . '<div class="gm-topic-body">' . $this->render_tags($m['tags']) . '</div>'
               . '</details>';

        // Formato
        $html .= '<details class="gm-topic-toggle" open>'
               . '<summary class="gm-topic-header">Calidad Markdown y Elementos Estructurales</summary>'
               . '<div class="gm-topic-body">' . $this->render_format($m['format']) . '</div>'
               . '</details>';

        $html .= '</div>';

        $html .= '<div class="gm-footer" style="margin-top: 25px; text-align: right;">'
               . get_string('last_updated', 'block_gitmetrics') . ': '
               . userdate($m['timestamp'])
               . '</div>';
        $html .= '</div>';
        return $html;
    }

    public function render_no_repo(): string {
        $html  = $this->styles();
        $html .= '<div class="gm-wrap gm-empty">';
        $html .= '<span class="gm-icon">[folder]</span>';
        $html .= '<p>' . get_string('no_repo_configured', 'block_gitmetrics') . '</p>';
        $html .= '</div>';
        return $html;
    }

    public function render_error(string $message): string {
        $html  = $this->styles();
        $html .= '<div class="gm-wrap gm-error-box">';
        $html .= '<span class="gm-icon">[!]</span>';
        $html .= '<p>' . html_writer::tag('strong', 'Error: ') . s($message) . '</p>';
        $html .= '</div>';
        return $html;
    }

    // ═════════════════════════════════════════════════════════════════════
    // Cabecera del repositorio
    // ═════════════════════════════════════════════════════════════════════

    private function render_repo_header(array $m): string {
        $repo_link = html_writer::link(
            $m['repo_url'],
            $m['owner'] . '/' . $m['repo'],
            ['target' => '_blank', 'rel' => 'noopener', 'class' => 'gm-repo-link']
        );
        $branch_badge = '<span class="gm-badge gm-badge-branch">⎇ ' . s($m['branch']) . '</span>';

        return '<div class="gm-header">'
             . '<div class="gm-header-title">' . get_string('pluginname', 'block_gitmetrics') . '</div>'
             . '<div class="gm-header-repo">' . $repo_link . ' ' . $branch_badge . '</div>'
             . '</div>';
    }

    // ═════════════════════════════════════════════════════════════════════
    // 1. Volumen y estructura
    // ═════════════════════════════════════════════════════════════════════

    public function render_volume(array $v): string {
        $html  = $this->section_open('[vol]', 'section_volume', 'gm-section-vol');

        // Fila de tarjetas principales
        $html .= '<div class="gm-cards">';
        $html .= $this->card(get_string('metric_md_files', 'block_gitmetrics'),   $v['md_file_count'],   'gm-card-blue');
        $html .= $this->card(get_string('metric_total_files', 'block_gitmetrics'), $v['total_file_count'], 'gm-card-indigo');
        $html .= $this->card(get_string('metric_dirs', 'block_gitmetrics'),        $v['dir_count'],        'gm-card-violet');
        $html .= $this->card(get_string('metric_max_depth', 'block_gitmetrics'),   $v['max_depth'],        'gm-card-slate');
        $html .= '</div>';

        // Segunda fila: tamaños y palabras
        $html .= '<div class="gm-cards">';
        $html .= $this->card(get_string('metric_total_size', 'block_gitmetrics'),  $this->fmt_bytes($v['total_size_bytes']), 'gm-card-teal');
        $html .= $this->card(get_string('metric_avg_size', 'block_gitmetrics'),    $this->fmt_bytes((int)$v['avg_size_bytes']), 'gm-card-teal');
        $html .= $this->card(get_string('metric_avg_words', 'block_gitmetrics'),   number_format($v['avg_word_count']) . ' ' . get_string('words', 'block_gitmetrics'), 'gm-card-emerald');
        $html .= $this->card(get_string('metric_max_words', 'block_gitmetrics'),   number_format($v['max_word_count']) . ' ' . get_string('words', 'block_gitmetrics'), 'gm-card-emerald');
        $html .= '</div>';

        // Archivos esenciales OKF
        $html .= '<div class="gm-subsection-title">' . get_string('essential_files', 'block_gitmetrics') . '</div>';
        $html .= '<div class="gm-essential">';
        foreach ($v['essential_files'] as $name => $info) {
            $ok    = $info['present'];
            $class = $ok ? 'gm-badge-ok' : 'gm-badge-missing';
            $icon  = $ok ? 'ok' : 'x';
            $title = $ok ? ($info['path'] ?? $name) : get_string('missing', 'block_gitmetrics');
            $html .= '<span class="gm-badge ' . $class . '" title="' . s($title) . '">'
                   . $icon . ' ' . htmlspecialchars($name) . '</span>';
        }
        $html .= '</div>';

        // Tabla de detalle por archivo (colapsable)
        if (!empty($v['files_detail'])) {
            $html .= $this->collapsible(
                get_string('files_detail', 'block_gitmetrics'),
                $this->files_table($v['files_detail'])
            );
        }

        $html .= $this->section_close();
        return $html;
    }

    // ═════════════════════════════════════════════════════════════════════
    // 2. Red y conectividad
    // ═════════════════════════════════════════════════════════════════════

    public function render_network(array $net): string {
        $html  = $this->section_open('[net]', 'section_network', 'gm-section-net');

        $html .= '<div class="gm-cards">';
        $html .= $this->card(get_string('metric_total_nodes', 'block_gitmetrics'),      $net['total_nodes'], 'gm-card-blue');
        $html .= $this->card(get_string('metric_avg_connections', 'block_gitmetrics'),  $net['avg_connections'], 'gm-card-indigo');
        $html .= $this->card(get_string('metric_total_links', 'block_gitmetrics'),      $net['total_internal_links'], 'gm-card-violet');
        $html .= '</div>';

        $html .= '<div class="gm-cards">';
        // Tasa de nodos huérfanos con indicador visual
        $orphan_color = $net['orphan_rate'] > 50 ? 'gm-card-red' : ($net['orphan_rate'] > 20 ? 'gm-card-orange' : 'gm-card-emerald');
        $html .= $this->card(get_string('metric_orphan_count', 'block_gitmetrics'), $net['orphan_count'], $orphan_color);
        $html .= $this->card(get_string('metric_orphan_rate', 'block_gitmetrics'),  $net['orphan_rate'] . '%', $orphan_color);
        $html .= $this->card_with_sub(
            get_string('metric_link_density', 'block_gitmetrics'),
            $net['link_density'],
            get_string('link_density_desc', 'block_gitmetrics'),
            'gm-card-teal'
        );
        $html .= '</div>';

        // Barra de progreso de nodos conectados
        if ($net['total_nodes'] > 0) {
            $connected_pct = round(100 - $net['orphan_rate'], 1);
            $html .= $this->progress_bar(
                get_string('metric_avg_connections', 'block_gitmetrics'),
                $connected_pct,
                $connected_pct > 50 ? '#10b981' : '#f59e0b'
            );
        }

        // Detalle de conectividad por nodo
        if (!empty($net['connectivity_detail'])) {
            $html .= $this->collapsible(
                get_string('metric_total_nodes', 'block_gitmetrics') . ' — ' . get_string('files_detail', 'block_gitmetrics'),
                $this->connectivity_table($net['connectivity_detail'])
            );
        }

        $html .= $this->section_close();
        return $html;
    }

    // ═════════════════════════════════════════════════════════════════════
    // 3. Etiquetas (tags)
    // ═════════════════════════════════════════════════════════════════════

    public function render_tags(array $tags): string {
        $html  = $this->section_open('[tags]', 'section_tags', 'gm-section-tags');

        $html .= '<div class="gm-cards">';
        $html .= $this->card(get_string('metric_unique_tags', 'block_gitmetrics'),      $tags['total_unique_tags'],  'gm-card-violet');
        $html .= $this->card(get_string('metric_tag_usage', 'block_gitmetrics'),        $tags['total_tag_usage'],    'gm-card-indigo');
        $html .= $this->card(get_string('metric_files_with_tags', 'block_gitmetrics'),  $tags['files_with_tags'],    'gm-card-emerald');
        $html .= $this->card(get_string('metric_files_without_tags', 'block_gitmetrics'), $tags['files_without_tags'], 'gm-card-orange');
        $html .= '</div>';

        $html .= '<div class="gm-cards">';
        $html .= $this->card_with_sub(
            get_string('metric_hamming_avg', 'block_gitmetrics'),
            $tags['hamming_avg'],
            get_string('hamming_desc', 'block_gitmetrics'),
            'gm-card-blue'
        );
        $html .= '</div>';

        // Nube de tags más usados
        if (!empty($tags['top_tags'])) {
            $html .= '<div class="gm-subsection-title">' . get_string('top_tags', 'block_gitmetrics') . '</div>';
            $html .= '<div class="gm-tagcloud">';
            $max_freq = max(array_values($tags['top_tags']));
            foreach ($tags['top_tags'] as $tag => $freq) {
                $size  = 11 + (int)round(($freq / max(1, $max_freq)) * 10);
                $html .= '<span class="gm-tag" style="font-size:' . $size . 'px">'
                       . s($tag) . ' <sup>' . $freq . '</sup></span>';
            }
            $html .= '</div>';
        }

        $html .= $this->section_close();
        return $html;
    }

    // ═════════════════════════════════════════════════════════════════════
    // 4. Validación de formato
    // ═════════════════════════════════════════════════════════════════════

    public function render_format(array $fmt): string {
        $html  = $this->section_open('[fmt]', 'section_format', 'gm-section-fmt');

        $html .= '<div class="gm-cards">';

        $fm_color  = $fmt['frontmatter_rate'] >= 80 ? 'gm-card-emerald' : ($fmt['frontmatter_rate'] >= 50 ? 'gm-card-orange' : 'gm-card-red');
        $md_color  = $fmt['valid_markdown_rate'] >= 90 ? 'gm-card-emerald' : ($fmt['valid_markdown_rate'] >= 70 ? 'gm-card-orange' : 'gm-card-red');

        $html .= $this->card(get_string('metric_frontmatter_rate', 'block_gitmetrics'),    $fmt['frontmatter_rate'] . '%',        $fm_color);
        $html .= $this->card(get_string('metric_valid_frontmatter', 'block_gitmetrics'),   $fmt['valid_frontmatter_rate'] . '%',  $fm_color);
        $html .= $this->card(get_string('metric_valid_markdown', 'block_gitmetrics'),      $fmt['valid_markdown_count'],          $md_color);
        $html .= $this->card(get_string('metric_valid_markdown_rate', 'block_gitmetrics'), $fmt['valid_markdown_rate'] . '%',     $md_color);
        $html .= '</div>';

        // Barras de progreso
        $html .= $this->progress_bar(
            get_string('metric_frontmatter_rate', 'block_gitmetrics'),
            $fmt['frontmatter_rate'],
            $fmt['frontmatter_rate'] >= 80 ? '#10b981' : '#f59e0b'
        );
        $html .= $this->progress_bar(
            get_string('metric_valid_markdown_rate', 'block_gitmetrics'),
            $fmt['valid_markdown_rate'],
            $fmt['valid_markdown_rate'] >= 90 ? '#10b981' : '#ef4444'
        );

        // Errores de frontmatter
        if (!empty($fmt['frontmatter_errors'])) {
            $error_html = '<ul class="gm-error-list">';
            foreach ($fmt['frontmatter_errors'] as $path => $errs) {
                foreach ($errs as $err) {
                    $error_html .= '<li><code>' . s($path) . '</code>: ' . s($err) . '</li>';
                }
            }
            $error_html .= '</ul>';
            $html .= $this->collapsible(get_string('frontmatter_errors', 'block_gitmetrics'), $error_html);
        }

        // Errores de Markdown
        if (!empty($fmt['markdown_errors'])) {
            $md_error_html = '<ul class="gm-error-list">';
            foreach ($fmt['markdown_errors'] as $path => $errs) {
                foreach ($errs as $err) {
                    $md_error_html .= '<li><code>' . s($path) . '</code>: ' . s($err) . '</li>';
                }
            }
            $md_error_html .= '</ul>';
            $html .= $this->collapsible('Markdown ' . get_string('frontmatter_errors', 'block_gitmetrics'), $md_error_html);
        }

        $html .= $this->section_close();
        return $html;
    }

    // ═════════════════════════════════════════════════════════════════════
    // Componentes de UI reutilizables
    // ═════════════════════════════════════════════════════════════════════

    private function section_open(string $icon, string $title_key, string $extra_class = ''): string {
        return '<div class="gm-section ' . $extra_class . '">'
             . '<div class="gm-section-header">'
             . '<span class="gm-section-icon">' . $icon . '</span>'
             . '<span class="gm-section-title">' . get_string($title_key, 'block_gitmetrics') . '</span>'
             . '</div>';
    }

    private function section_close(): string {
        return '</div>';
    }

    private function card(string $label, $value, string $color_class = 'gm-card-blue'): string {
        return '<div class="gm-card ' . $color_class . '">'
             . '<div class="gm-card-value">' . htmlspecialchars((string)$value) . '</div>'
             . '<div class="gm-card-label">' . htmlspecialchars($label) . '</div>'
             . '</div>';
    }

    private function card_with_sub(string $label, $value, string $sub, string $color_class = 'gm-card-blue'): string {
        return '<div class="gm-card ' . $color_class . '">'
             . '<div class="gm-card-value">' . htmlspecialchars((string)$value) . '</div>'
             . '<div class="gm-card-label">' . htmlspecialchars($label) . '</div>'
             . '<div class="gm-card-sub">' . htmlspecialchars($sub) . '</div>'
             . '</div>';
    }

    private function progress_bar(string $label, float $pct, string $color): string {
        $pct = min(100, max(0, $pct));
        return '<div class="gm-progress-wrap">'
             . '<div class="gm-progress-label">' . htmlspecialchars($label) . ' <strong>' . $pct . '%</strong></div>'
             . '<div class="gm-progress-track">'
             . '<div class="gm-progress-fill" style="width:' . $pct . '%;background:' . $color . '"></div>'
             . '</div></div>';
    }

    private function collapsible(string $summary, string $content): string {
        return '<details class="gm-details">'
             . '<summary class="gm-summary">' . htmlspecialchars($summary) . '</summary>'
             . '<div class="gm-details-content">' . $content . '</div>'
             . '</details>';
    }

    private function files_table(array $files): string {
        $html  = '<table class="gm-table"><thead><tr>'
               . '<th>Archivo</th><th>Tamaño</th><th>Palabras</th><th></th>'
               . '</tr></thead><tbody>';
        foreach ($files as $f) {
            $viewer_url   = $this->file_viewer_url($f['path']); // ya HTML-safe, NO usar s()
            $external_url = $this->file_external_url($f['path']);
            $html .= '<tr>'
                   . '<td>'
                   .   '<a href="' . $viewer_url . '" class="gm-file-link" title="Ver archivo en Moodle">'
                   .     '<code>' . s($f['path']) . '</code>'
                   .   '</a>'
                   . '</td>'
                   . '<td>' . $this->fmt_bytes($f['size_bytes']) . '</td>'
                   . '<td>' . number_format($f['word_count']) . '</td>'
                   . '<td style="white-space:nowrap">'
                   .   '<a href="' . s($external_url) . '" target="_blank" rel="noopener" class="gm-ext-link" title="Ver en repositorio externo">↗</a>'
                   . '</td>'
                   . '</tr>';
        }
        $html .= '</tbody></table>';
        return $html;
    }

    private function connectivity_table(array $detail): string {
        $html  = '<table class="gm-table"><thead><tr>'
               . '<th>Archivo</th><th>Salientes</th><th>Entrantes</th><th>Estado</th><th></th>'
               . '</tr></thead><tbody>';
        foreach ($detail as $d) {
            $status = $d['is_orphan']
                ? '<span class="gm-badge gm-badge-missing">Huérfano</span>'
                : '<span class="gm-badge gm-badge-ok">Conectado</span>';
            $viewer_url   = $this->file_viewer_url($d['path']); // ya HTML-safe, NO usar s()
            $external_url = $this->file_external_url($d['path']);
            $html .= '<tr>'
                   . '<td>'
                   .   '<a href="' . $viewer_url . '" class="gm-file-link" title="Ver archivo en Moodle">'
                   .     '<code>' . s($d['path']) . '</code>'
                   .   '</a>'
                   . '</td>'
                   . '<td>' . $d['outgoing'] . '</td>'
                   . '<td>' . ($d['has_incoming'] ? 'Si' : 'No') . '</td>'
                   . '<td>' . $status . '</td>'
                   . '<td style="white-space:nowrap">'
                   .   '<a href="' . s($external_url) . '" target="_blank" rel="noopener" class="gm-ext-link" title="Ver en repositorio externo">↗</a>'
                   . '</td>'
                   . '</tr>';
        }
        $html .= '</tbody></table>';
        return $html;
    }

    // ═════════════════════════════════════════════════════════════════════
    // Utilidades
    // ═════════════════════════════════════════════════════════════════════

    private function fmt_bytes(int $bytes): string {
        if ($bytes < 1024)       return $bytes . ' B';
        if ($bytes < 1048576)    return round($bytes / 1024, 1) . ' KB';
        return round($bytes / 1048576, 2) . ' MB';
    }

    // ═════════════════════════════════════════════════════════════════════
    // CSS inline (se inyecta una sola vez en el bloque)
    // ═════════════════════════════════════════════════════════════════════

    public function styles(): string {
        return <<<CSS
<style>
/* ── block_gitmetrics: estilos del bloque ──────────────────────── */
.gm-wrap {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 13px;
  color: #1e293b;
  line-height: 1.5;
}
/* Cabecera */
.gm-header {
  background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 10px;
  color: #fff;
}
.gm-header-title { font-size: 13px; font-weight: 700; opacity: .85; margin-bottom: 4px; }
.gm-header-repo  { font-size: 14px; font-weight: 600; }
.gm-repo-link    { color: #93c5fd; text-decoration: none; }
.gm-repo-link:hover { text-decoration: underline; }
.gm-badge-branch { background: rgba(255,255,255,.2); color: #fff; border-radius: 4px; padding: 1px 7px; font-size: 11px; }

/* Secciones */
.gm-section {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 10px;
}
.gm-section-header { display: flex; align-items: center; gap: 6px; margin-bottom: 10px; }
.gm-section-icon   { font-size: 16px; }
.gm-section-title  { font-weight: 700; font-size: 13px; color: #334155; text-transform: uppercase; letter-spacing: .4px; }
.gm-subsection-title { font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; margin: 10px 0 6px; letter-spacing: .3px; }

/* Tarjetas de métricas */
.gm-cards { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 8px; }
.gm-card  {
  flex: 1 1 calc(25% - 7px); min-width: 70px;
  border-radius: 8px; padding: 9px 10px; text-align: center;
}
.gm-card-value { font-size: 18px; font-weight: 800; line-height: 1.1; }
.gm-card-label { font-size: 10px; margin-top: 3px; opacity: .85; line-height: 1.3; }
.gm-card-sub   { font-size: 9px; margin-top: 3px; opacity: .7; }

/* Paleta de colores de tarjetas */
.gm-card-blue    { background:#dbeafe; color:#1e40af; }
.gm-card-indigo  { background:#e0e7ff; color:#3730a3; }
.gm-card-violet  { background:#ede9fe; color:#5b21b6; }
.gm-card-slate   { background:#f1f5f9; color:#334155; border:1px solid #cbd5e1; }
.gm-card-teal    { background:#ccfbf1; color:#0f766e; }
.gm-card-emerald { background:#d1fae5; color:#065f46; }
.gm-card-orange  { background:#ffedd5; color:#9a3412; }
.gm-card-red     { background:#fee2e2; color:#991b1b; }

/* Badges esenciales */
.gm-essential { display: flex; flex-wrap: wrap; gap: 6px; }
.gm-badge     { display: inline-block; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600; }
.gm-badge-ok      { background: #d1fae5; color: #065f46; }
.gm-badge-missing { background: #fee2e2; color: #991b1b; }

/* Barra de progreso */
.gm-progress-wrap  { margin: 6px 0; }
.gm-progress-label { font-size: 11px; color: #475569; margin-bottom: 3px; }
.gm-progress-track { background: #e2e8f0; border-radius: 99px; height: 7px; overflow: hidden; }
.gm-progress-fill  { height: 100%; border-radius: 99px; transition: width .4s ease; }

/* Nube de tags */
.gm-tagcloud { display: flex; flex-wrap: wrap; gap: 5px; padding: 5px 0; }
.gm-tag {
  display: inline-block;
  background: #ede9fe; color: #5b21b6;
  border-radius: 99px; padding: 2px 10px;
  font-weight: 600; white-space: nowrap;
}
.gm-tag sup { font-size: 9px; opacity: .7; }

/* Colapsibles */
.gm-details { margin-top: 8px; }
.gm-summary {
  font-size: 11px; font-weight: 600; color: #475569; cursor: pointer;
  padding: 4px 0; list-style: none; user-select: none;
}
.gm-summary::before { content: '▶ '; font-size: 9px; }
details[open] .gm-summary::before { content: '▼ '; }
.gm-details-content { margin-top: 6px; overflow-x: auto; }

/* Temas en toggle / acordeón a página completa */
.gm-topic-toggle {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.04);
  overflow: hidden;
  margin-bottom: 6px;
}
.gm-topic-header {
  background: #f8fafc;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  padding: 14px 18px;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  display: block;
  list-style: none;
}
details[open].gm-topic-toggle .gm-topic-header {
  border-bottom: 1px solid #e2e8f0;
  background: #f1f5f9;
}
.gm-topic-header::before { content: '▶ '; font-size: 11px; margin-right: 6px; }
details[open] .gm-topic-header::before { content: '▼ '; }
.gm-topic-body { padding: 18px; }

/* Tablas */
.gm-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.gm-table th { background: #f1f5f9; color: #334155; font-weight: 700; padding: 4px 8px; text-align: left; border-bottom: 1px solid #cbd5e1; }
.gm-table td { padding: 4px 8px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.gm-table tr:hover td { background: #f8fafc; }
.gm-table code { font-size: 10px; background: #f1f5f9; border-radius: 3px; padding: 1px 4px; word-break: break-all; }

/* Enlace de archivo en tabla (visor integrado) */
.gm-file-link { text-decoration: none; color: inherit; }
.gm-file-link:hover code { background: #dbeafe; color: #1e40af; }

/* Icono de enlace externo ↗ */
.gm-ext-link {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 4px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  transition: background .15s;
}
.gm-ext-link:hover { background: #2563eb; color: #fff; text-decoration: none; }

/* Lista de errores */
.gm-error-list { margin: 4px 0; padding-left: 18px; font-size: 11px; color: #7c3aed; }
.gm-error-list code { font-size: 10px; background: #ede9fe; border-radius: 3px; padding: 1px 4px; }

/* Footer */
.gm-footer { font-size: 10px; color: #94a3b8; text-align: right; margin-top: 4px; }

/* Estado vacío / error */
.gm-empty, .gm-error-box {
  text-align: center; padding: 20px; background: #f8fafc;
  border-radius: 10px; border: 1px dashed #cbd5e1; color: #64748b;
}
.gm-error-box { background: #fff7f7; border-color: #fca5a5; color: #7f1d1d; }
.gm-icon { font-size: 28px; display: block; margin-bottom: 8px; }
</style>
CSS;
    }
}
