<?php
// ─────────────────────────────────────────────────────────────────────────────
// view_file.php – Visor de archivos Markdown en vivo desde el repositorio Git.
//
// Características:
//  · Parsea frontmatter YAML y lo renderiza como ficha elegante
//  · Convierte [[wiki-links]] de estilo Obsidian en hipervínculos Moodle
//  · Renderiza el cuerpo Markdown con format_text
//  · No almacena ningún archivo en disco — todo en memoria RAM
// ─────────────────────────────────────────────────────────────────────────────

require_once(__DIR__ . '/../../config.php');
require_once($CFG->libdir . '/filelib.php');

// ── Parámetros de entrada ────────────────────────────────────────────────────
$courseid = optional_param('courseid', SITEID, PARAM_INT);
$blockid  = optional_param('blockid', 0, PARAM_INT);
$filepath = optional_param('path', '', PARAM_TEXT);
$repourl  = optional_param('repo_url', '', PARAM_RAW);
$branch   = optional_param('branch', 'main', PARAM_TEXT);

// ── Autenticación ────────────────────────────────────────────────────────────
$course = $DB->get_record('course', ['id' => max(1, $courseid)], '*', MUST_EXIST);
require_login($course);

// ── Mostrar página de error si faltan params esenciales ─────────────────────
if (empty($filepath) || empty($repourl)) {
    $PAGE->set_url('/blocks/gitmetrics/view_file.php');
    $PAGE->set_title('Error — Parámetros incorrectos');
    $PAGE->set_heading($course->fullname);
    $PAGE->set_pagelayout('report');
    echo $OUTPUT->header();
    echo '<div style="font-family:monospace;padding:20px;background:#1e293b;color:#e2e8f0;border-radius:8px;margin:20px;">';
    echo '<h2 style="color:#f59e0b">⚠️ Parámetros incorrectos</h2>';
    echo '<pre>' . htmlspecialchars(print_r($_GET, true)) . '</pre>';
    echo '<p>REQUEST_URI: ' . htmlspecialchars($_SERVER['REQUEST_URI'] ?? '') . '</p>';
    echo '</div>';
    echo $OUTPUT->footer();
    exit;
}

require_capability('block/gitmetrics:viewmetrics', context_course::instance($course->id));

// ── Determinar proveedor y token ─────────────────────────────────────────────
if (str_contains($repourl, 'github.com')) {
    $provider   = 'github';
    $token      = get_config('block_gitmetrics', 'github_token') ?: '';
    $gitlab_url = 'https://gitlab.com';
} else {
    $provider   = 'gitlab';
    $token      = get_config('block_gitmetrics', 'gitlab_token') ?: '';
    $gitlab_url = get_config('block_gitmetrics', 'gitlab_url') ?: 'https://gitlab.com';
}

// ── Extraer owner y repo de la URL del repositorio ──────────────────────────
$parsed     = parse_url($repourl);
$path_parts = array_values(array_filter(explode('/', trim($parsed['path'] ?? '', '/'))));
if (count($path_parts) < 2) {
    print_error('error_invalid_url', 'block_gitmetrics');
}
$owner = $path_parts[0];
$repo  = $path_parts[1];

// ── URL externa (GitLab / GitHub) para el botón ↗ ───────────────────────────
if ($provider === 'github') {
    $external_url = "https://github.com/{$owner}/{$repo}/blob/{$branch}/" . str_replace('%2F', '/', rawurlencode($filepath));
} else {
    $external_url = rtrim($gitlab_url, '/') . "/{$owner}/{$repo}/-/blob/{$branch}/" . str_replace('%2F', '/', rawurlencode($filepath));
}

// ── Descargar contenido raw en memoria (sin guardar en disco) ───────────────
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/gitlab_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/github_client.php');

$raw_content = null;
$fetch_error = null;
try {
    if ($provider === 'github') {
        $client = new \block_gitmetrics\github_client($token);
    } else {
        $client = new \block_gitmetrics\gitlab_client($gitlab_url, $token);
    }
    $raw_content = $client->get_file_content($owner, $repo, $filepath, $branch);
} catch (\Exception $e) {
    $fetch_error = $e->getMessage();
}

// ═════════════════════════════════════════════════════════════════════════════
// Funciones de procesamiento de Markdown / Frontmatter / Wiki-links
// ═════════════════════════════════════════════════════════════════════════════

/**
 * Extrae y parsea el frontmatter YAML (entre ---) del inicio del documento.
 * Devuelve ['meta' => [...campos...], 'body' => '...resto del contenido...'].
 */
function gmv_parse_frontmatter(string $content): array {
    $meta = [];
    $body = $content;

    if (preg_match('/^---\s*\n(.*?)\n---\s*\n?(.*)/s', $content, $m)) {
        $yaml = $m[1];
        $body = ltrim($m[2]);
        // Parsear campo a campo
        $lines   = explode("\n", $yaml);
        $cur_key = null;
        foreach ($lines as $line) {
            if (trim($line) === '') continue;
            // Lista inline: key: [a, b, c]
            if (preg_match('/^([a-zA-Z_][a-zA-Z0-9_]*):\s*\[([^\]]*)\]\s*$/', $line, $lm)) {
                $cur_key       = $lm[1];
                $raw_arr       = trim($lm[2]);
                $meta[$cur_key] = $raw_arr === ''
                    ? []
                    : array_map('trim', explode(',', $raw_arr));
                continue;
            }
            // Clave escalar: key: value
            if (preg_match('/^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)?$/', $line, $lm)) {
                $cur_key        = $lm[1];
                $val            = trim($lm[2] ?? '');
                $meta[$cur_key] = $val;
                continue;
            }
            // Elemento de lista YAML: - item
            if ($cur_key && preg_match('/^\s+-\s+(.+)$/', $line, $lm)) {
                if (!is_array($meta[$cur_key])) $meta[$cur_key] = [];
                $meta[$cur_key][] = trim($lm[1]);
            }
        }
    }
    return ['meta' => $meta, 'body' => $body];
}

/**
 * Convierte [[path|Texto]] y [[path]] (Obsidian wiki-links) en hipervínculos
 * de Markdown hacia view_file.php con los parámetros del contexto actual.
 * Usa out(false) para que format_text no doble-codifique las URLs.
 */
function gmv_convert_wiki_links(string $body, string $repourl, string $branch, int $courseid, int $blockid): string {
    // Directorio base del archivo actual (para resolver paths relativos)
    // No lo necesitamos aquí porque los wiki-links suelen ser paths completos

    $replace = function(array $m) use ($repourl, $branch, $courseid, $blockid): string {
        // $m[1] = path, $m[2] = texto (si existe)
        $wpath   = trim($m[1]);
        $display = isset($m[2]) ? trim($m[2]) : basename($wpath);
        // Añadir extensión .md si no la tiene
        if (!str_ends_with(strtolower($wpath), '.md')) {
            $wpath .= '.md';
        }
        $url = (new moodle_url('/blocks/gitmetrics/view_file.php', [
            'courseid' => $courseid,
            'blockid'  => $blockid,
            'path'     => $wpath,
            'repo_url' => $repourl,
            'branch'   => $branch,
        ]))->out(false); // out(false) → raw URL para embeber en Markdown
        return '[' . $display . '](' . $url . ')';
    };

    // [[path|Texto de enlace]]
    $body = preg_replace_callback('/\[\[([^\]|#]+)(?:#[^\]|]*)?\|([^\]]+)\]\]/', $replace, $body);
    // [[path]] sin texto
    $body = preg_replace_callback('/\[\[([^\]|#]+)(?:#[^\]|]*)?\]\]/', function($m) use ($replace) {
        return $replace([$m[0], $m[1]]);
    }, $body);

    return $body;
}

/**
 * Genera la ficha de metadatos (frontmatter) renderizada en HTML.
 */
function gmv_render_meta_card(array $meta, string $repourl, string $branch, int $courseid, int $blockid): string {
    if (empty($meta)) return '';

    // Colores y emojis por tipo
    $type_config = [
        'Concept'  => ['🧠', '#7c3aed', '#ede9fe'],
        'Entity'   => ['🏛️', '#0f766e', '#ccfbf1'],
        'Source'   => ['📚', '#b45309', '#fef3c7'],
        'Index'    => ['🗂️', '#1e40af', '#dbeafe'],
        'Log'      => ['📋', '#374151', '#f3f4f6'],
        'Playbook' => ['⚡', '#be185d', '#fce7f3'],
    ];
    $type      = $meta['type'] ?? '';
    $tc        = $type_config[$type] ?? ['📄', '#334155', '#f1f5f9'];
    $icon      = $tc[0]; $color = $tc[1]; $bg = $tc[2];

    $title       = $meta['title']       ?? '';
    $description = $meta['description'] ?? '';
    $tags        = (array)($meta['tags'] ?? []);
    $timestamp   = $meta['timestamp']   ?? '';
    $resource    = $meta['resource']    ?? '';
    $claims      = (array)($meta['claims'] ?? []);

    $h  = '<div class="gmv-meta-card">';

    // Cabecera tipo + título
    $h .= '<div class="gmv-meta-header" style="background:' . $bg . ';border-left:4px solid ' . $color . ';">';
    if ($type) {
        $h .= '<span class="gmv-meta-type" style="color:' . $color . ';">' . $icon . ' ' . htmlspecialchars($type) . '</span>';
    }
    if ($title) {
        $h .= '<h1 class="gmv-meta-title">' . htmlspecialchars($title) . '</h1>';
    }
    $h .= '</div>';

    // Descripción
    if ($description) {
        $h .= '<div class="gmv-meta-desc">' . htmlspecialchars($description) . '</div>';
    }

    // Recurso relacionado (con wiki-link si contiene path)
    if ($resource) {
        $res_path = trim($resource);
        if (!str_ends_with(strtolower($res_path), '.md')) $res_path .= '.md';
        $res_url = (new moodle_url('/blocks/gitmetrics/view_file.php', [
            'courseid' => $courseid,
            'blockid'  => $blockid,
            'path'     => $res_path,
            'repo_url' => $repourl,
            'branch'   => $branch,
        ]))->out();
        $h .= '<div class="gmv-meta-row">';
        $h .= '<span class="gmv-meta-label">📎 Recurso:</span>';
        $h .= '<a href="' . $res_url . '" class="gmv-meta-link">' . htmlspecialchars(basename($res_path)) . '</a>';
        $h .= '</div>';
    }

    // Tags
    if (!empty($tags)) {
        $tags_clean = array_filter(array_map('trim', $tags));
        if (!empty($tags_clean)) {
            $h .= '<div class="gmv-meta-row gmv-meta-tags">';
            $h .= '<span class="gmv-meta-label">🏷️ Tags:</span>';
            foreach ($tags_clean as $tag) {
                $h .= '<span class="gmv-tag">' . htmlspecialchars($tag) . '</span>';
            }
            $h .= '</div>';
        }
    }

    // Claims
    if (!empty($claims)) {
        $claims_clean = array_filter(array_map('trim', $claims));
        if (!empty($claims_clean)) {
            $h .= '<div class="gmv-meta-row">';
            $h .= '<span class="gmv-meta-label">💡 Afirmaciones:</span>';
            $h .= '<ul class="gmv-claims-list">';
            foreach ($claims_clean as $claim) {
                $h .= '<li>' . htmlspecialchars($claim) . '</li>';
            }
            $h .= '</ul>';
            $h .= '</div>';
        }
    }

    // Timestamp
    if ($timestamp) {
        try {
            $ts = new DateTime($timestamp);
            $ts_fmt = $ts->format('d/m/Y H:i');
        } catch (\Exception $e) {
            $ts_fmt = $timestamp;
        }
        $h .= '<div class="gmv-meta-ts">🕐 Actualizado: ' . htmlspecialchars($ts_fmt) . '</div>';
    }

    $h .= '</div>';
    return $h;
}

// ═════════════════════════════════════════════════════════════════════════════
// Procesar el contenido del archivo
// ═════════════════════════════════════════════════════════════════════════════

$meta_card_html = '';
$body_html      = '';

if ($raw_content !== null) {
    // 1. Extraer frontmatter
    $parsed_doc  = gmv_parse_frontmatter($raw_content);
    $meta        = $parsed_doc['meta'];
    $body_text   = $parsed_doc['body'];

    // 2. Renderizar ficha de metadatos
    $meta_card_html = gmv_render_meta_card($meta, $repourl, $branch, $courseid, $blockid);

    // 3. Convertir [[wiki-links]] antes del render Markdown
    $body_text = gmv_convert_wiki_links($body_text, $repourl, $branch, $courseid, $blockid);

    // 4. Convertir Markdown a HTML en memoria
    $ctx       = context_course::instance($course->id);
    $body_html = format_text($body_text, FORMAT_MARKDOWN, [
        'noclean' => false,
        'trusted' => false,
        'context' => $ctx,
        'filter'  => false,
    ]);
}

// ── Título de la página ──────────────────────────────────────────────────────
$doc_title  = !empty($meta['title']) ? $meta['title'] : basename($filepath);
$page_title = $doc_title . ' — ' . $owner . '/' . $repo;

$PAGE->set_url('/blocks/gitmetrics/view_file.php', [
    'courseid' => $courseid,
    'blockid'  => $blockid,
    'path'     => $filepath,
    'repo_url' => $repourl,
    'branch'   => $branch,
]);
$PAGE->set_title($page_title);
$PAGE->set_heading($course->fullname);
$PAGE->set_pagelayout('report');

// ── URL de vuelta ────────────────────────────────────────────────────────────
$back_url = new moodle_url('/blocks/gitmetrics/view.php', [
    'courseid' => $courseid,
    'blockid'  => $blockid,
]);

echo $OUTPUT->header();
?>
<style>
/* ── Visor Markdown: estilos ────────────────────────────────────────────── */
.gmv-wrap {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 860px;
  margin: 0 auto;
  padding: 20px 0 60px;
}

/* Barra superior */
.gmv-topbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 10px; margin-bottom: 18px;
}
.gmv-breadcrumb {
  font-size: 12px; color: #64748b;
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.gmv-breadcrumb a { color: #2563eb; text-decoration: none; }
.gmv-breadcrumb a:hover { text-decoration: underline; }
.gmv-path-badge {
  background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px;
  padding: 3px 10px; font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 11px; color: #334155;
}
.gmv-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.gmv-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600;
  text-decoration: none; border: 1px solid transparent; transition: background .15s;
}
.gmv-btn-back { background: #f1f5f9; color: #334155; border-color: #e2e8f0; }
.gmv-btn-back:hover { background: #e2e8f0; text-decoration: none; color: #1e293b; }
.gmv-btn-ext  { background: #2563eb; color: #fff; }
.gmv-btn-ext:hover  { background: #1d4ed8; text-decoration: none; color: #fff; }

/* Tarjeta principal */
.gmv-card {
  background: #fff; border: 1px solid #e2e8f0;
  border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,.07); overflow: hidden;
}
.gmv-card-topbar {
  background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%);
  padding: 12px 20px; color: #fff;
  display: flex; align-items: center; justify-content: space-between;
}
.gmv-card-filename { font-size: 13px; font-weight: 700; font-family: monospace; opacity:.9; }
.gmv-branch-badge {
  background: rgba(255,255,255,.2); color: #fff;
  border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: 600;
}

/* Ficha de metadatos (frontmatter) */
.gmv-meta-card {
  border-bottom: 1px solid #e2e8f0;
  padding: 20px 28px;
}
.gmv-meta-header {
  border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;
}
.gmv-meta-type {
  display: inline-block; font-size: 11px; font-weight: 800;
  text-transform: uppercase; letter-spacing: .6px; margin-bottom: 6px;
}
.gmv-meta-title {
  font-size: 22px; font-weight: 800; color: #0f172a;
  margin: 0; line-height: 1.25;
}
.gmv-meta-desc {
  font-size: 14px; color: #475569; line-height: 1.65;
  margin-bottom: 14px; padding: 12px 16px;
  background: #f8fafc; border-radius: 8px; border-left: 3px solid #cbd5e1;
}
.gmv-meta-row {
  display: flex; align-items: flex-start; gap: 10px;
  margin-bottom: 10px; flex-wrap: wrap;
}
.gmv-meta-label {
  font-size: 11px; font-weight: 700; color: #94a3b8;
  text-transform: uppercase; letter-spacing: .4px;
  min-width: 90px; padding-top: 3px; flex-shrink: 0;
}
.gmv-meta-link {
  color: #2563eb; font-size: 13px; text-decoration: none;
  font-family: monospace; background: #eff6ff; padding: 2px 8px; border-radius: 4px;
}
.gmv-meta-link:hover { text-decoration: underline; }
.gmv-meta-tags { align-items: center; }
.gmv-tag {
  display: inline-block; background: #ede9fe; color: #5b21b6;
  border-radius: 99px; padding: 2px 10px; font-size: 11px; font-weight: 600;
}
.gmv-claims-list {
  margin: 4px 0; padding-left: 18px; font-size: 13px; color: #374151; flex: 1;
}
.gmv-claims-list li { margin-bottom: 4px; }
.gmv-meta-ts {
  font-size: 11px; color: #94a3b8; text-align: right; margin-top: 8px;
  border-top: 1px solid #f1f5f9; padding-top: 8px;
}

/* Cuerpo del documento (Markdown renderizado) */
.gmv-body {
  padding: 28px 32px;
  font-size: 15px; line-height: 1.8; color: #1e293b;
}
.gmv-body h1 {
  font-size: 1.65em; font-weight: 800; color: #0f172a;
  border-bottom: 2px solid #e2e8f0; padding-bottom: .3em; margin: 0 0 .6em;
}
.gmv-body h2 { font-size: 1.3em; font-weight: 700; color: #1e293b; margin: 1.4em 0 .5em; }
.gmv-body h3 { font-size: 1.1em; font-weight: 700; color: #334155; margin: 1.2em 0 .4em; }
.gmv-body h4, .gmv-body h5, .gmv-body h6 { font-size: 1em; font-weight: 700; color: #475569; margin: 1em 0 .4em; }
.gmv-body p  { margin: 0 0 1em; }
.gmv-body ul, .gmv-body ol { margin: 0 0 1em 1.6em; }
.gmv-body li { margin-bottom: .35em; }
.gmv-body a  { color: #2563eb; text-decoration: none; border-bottom: 1px solid #93c5fd; transition: color .15s; }
.gmv-body a:hover { color: #1d4ed8; border-color: #1d4ed8; }
.gmv-body pre {
  background: #0f172a; color: #e2e8f0; border-radius: 10px;
  padding: 18px 22px; overflow-x: auto; font-size: 13px; margin: 1.2em 0;
}
.gmv-body code {
  font-family: 'SFMono-Regular', Consolas, monospace;
  background: #f1f5f9; color: #7c3aed; border-radius: 4px; padding: 1px 6px; font-size: .9em;
}
.gmv-body pre code { background: none; color: inherit; padding: 0; }
.gmv-body blockquote {
  border-left: 4px solid #2563eb; margin: 1em 0; padding: .6em 1.2em;
  background: #eff6ff; border-radius: 0 8px 8px 0; color: #1e40af;
}
.gmv-body table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 14px; }
.gmv-body th { background: #f1f5f9; color: #334155; font-weight: 700; padding: 9px 13px; border: 1px solid #e2e8f0; text-align: left; }
.gmv-body td { padding: 8px 13px; border: 1px solid #e2e8f0; vertical-align: top; }
.gmv-body tr:nth-child(even) td { background: #f8fafc; }
.gmv-body img { max-width: 100%; border-radius: 8px; margin: .6em 0; box-shadow: 0 2px 8px rgba(0,0,0,.1); }
.gmv-body hr  { border: none; border-top: 2px solid #e2e8f0; margin: 1.8em 0; }
.gmv-body strong { font-weight: 700; color: #0f172a; }
.gmv-body em { font-style: italic; color: #374151; }

/* Footer */
.gmv-footer-note {
  font-size: 11px; color: #94a3b8; text-align: right; margin-top: 12px;
}

/* Error */
.gmv-error-box {
  text-align: center; padding: 40px; color: #7f1d1d;
  background: #fff7f7; border-radius: 8px; border: 1px dashed #fca5a5; margin: 20px 28px;
}
</style>

<div class="gmv-wrap">

  <!-- Barra superior -->
  <div class="gmv-topbar">
    <div class="gmv-breadcrumb">
      <a href="<?php echo $back_url->out(); ?>">📊 Métricas</a>
      <span style="color:#cbd5e1">›</span>
      <span class="gmv-path-badge">📄 <?php echo s($filepath); ?></span>
    </div>
    <div class="gmv-actions">
      <a href="<?php echo $back_url->out(); ?>" class="gmv-btn gmv-btn-back">← Volver</a>
      <a href="<?php echo s($external_url); ?>" target="_blank" rel="noopener" class="gmv-btn gmv-btn-ext">
        ↗ Ver en <?php echo ($provider === 'github') ? 'GitHub' : 'GitLab'; ?>
      </a>
    </div>
  </div>

  <!-- Tarjeta principal -->
  <div class="gmv-card">

    <!-- Topbar azul con nombre de archivo y rama -->
    <div class="gmv-card-topbar">
      <div class="gmv-card-filename">📄 <?php echo s(basename($filepath)); ?></div>
      <span class="gmv-branch-badge">⎇ <?php echo s($branch); ?></span>
    </div>

<?php if ($raw_content !== null): ?>

    <!-- Ficha de metadatos (frontmatter) -->
<?php if (!empty($meta_card_html)): ?>
    <?php echo $meta_card_html; ?>
<?php endif; ?>

    <!-- Cuerpo del documento -->
    <div class="gmv-body">
      <?php echo $body_html; ?>
    </div>

<?php else: ?>
    <div class="gmv-error-box">
      <div style="font-size:32px;margin-bottom:10px;">⚠️</div>
      <strong>No se pudo cargar el archivo</strong>
      <?php if (!empty($fetch_error)): ?>
        <p style="margin-top:8px;font-size:13px;"><?php echo s($fetch_error); ?></p>
      <?php endif; ?>
    </div>
<?php endif; ?>

  </div><!-- .gmv-card -->

  <div class="gmv-footer-note">
    📡 Contenido cargado en tiempo real desde el repositorio remoto.
    No se almacena ningún archivo en el servidor de Moodle.
  </div>

</div><!-- .gmv-wrap -->

<?php
echo $OUTPUT->footer();
