<?php
// -----------------------------------------------------------------------------
// Página completa de visualización de métricas de la Base de Conocimiento Git
// -----------------------------------------------------------------------------

require_once(__DIR__ . '/../../config.php');

$courseid = optional_param('courseid', SITEID, PARAM_INT);
$blockid  = optional_param('blockid', 0, PARAM_INT);

$course = $DB->get_record('course', ['id' => $courseid], '*', MUST_EXIST);
require_login($course);

$PAGE->set_url('/blocks/gitmetrics/view.php', ['courseid' => $courseid, 'blockid' => $blockid]);
$PAGE->set_title(get_string('pluginname', 'block_gitmetrics'));
$PAGE->set_heading($course->fullname);
$PAGE->set_pagelayout('report');

// Obtener configuración de la instancia del bloque
$repourl = '';
$branch  = 'main';

if ($blockid > 0 && ($instance = $DB->get_record('block_instances', ['id' => $blockid]))) {
    if (!empty($instance->configdata)) {
        $config = unserialize(base64_decode($instance->configdata));
        if (!empty($config->github_url)) {
            $repourl = trim($config->github_url);
        }
        if (!empty($config->branch)) {
            $branch = trim($config->branch);
        }
    }
}

echo $OUTPUT->header();

if (empty($repourl)) {
    echo $OUTPUT->notification(get_string('no_repo_configured', 'block_gitmetrics'), 'warning');
    echo $OUTPUT->footer();
    exit;
}

$cache   = new \block_gitmetrics\metrics_cache();
$metrics = $cache->get($repourl, $blockid);

if ($metrics === null) {
    $token      = get_config('block_gitmetrics', 'github_token') ?: '';
    $calculator = new \block_gitmetrics\metrics_calculator($token);
    $metrics    = $calculator->calculate($repourl, $branch);
    $cache->set($repourl, $blockid, $metrics);
}

$renderer = $PAGE->get_renderer('block_gitmetrics');

echo '<div class="container-fluid" style="max-width: 1300px; margin: 0 auto; padding: 20px 0;">';
echo $renderer->render_fullpage_metrics($metrics);
echo '</div>';

echo $OUTPUT->footer();
