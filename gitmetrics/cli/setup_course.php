<?php
// -----------------------------------------------------------------------------
// Script CLI para crear la asignatura "Panel de Métricas y BdC"
// -----------------------------------------------------------------------------

define('CLI_SCRIPT', true);

require_once(__DIR__ . '/../../../config.php');
require_once($CFG->dirroot . '/course/lib.php');

global $DB;

$shortname = 'METRICAS_BDC';
$course = $DB->get_record('course', ['shortname' => $shortname]);

if (!$course) {
    $data = new stdClass();
    $data->fullname  = 'Panel de Métricas y BdC';
    $data->shortname = $shortname;
    $data->category  = 1;
    $data->summary   = 'Asignatura y panel central dedicado a evaluar Bases de Conocimiento Git.';
    $data->format    = 'topics';
    $data->visible   = 1;

    $course = create_course($data);
    echo "Asignatura 'Panel de Métricas y BdC' creada con éxito (ID: {$course->id}).\n";
} else {
    echo "Asignatura 'Panel de Métricas y BdC' ya existía (ID: {$course->id}).\n";
}

// Asegurar que exista el bloque en este curso
$context = context_course::instance($course->id);
if (!$DB->record_exists('block_instances', ['blockname' => 'gitmetrics', 'parentcontextid' => $context->id])) {
    $instance = new stdClass();
    $instance->blockname = 'gitmetrics';
    $instance->parentcontextid = $context->id;
    $instance->showinsubcontexts = 0;
    $instance->pagetypepattern = 'course-view-*';
    $instance->subpagepattern = null;
    $instance->defaultregion = 'side-pre';
    $instance->defaultweight = 0;
    $instance->configdata = base64_encode(serialize((object)[
        'github_url' => 'https://github.com/julia8873/bdc-prueba',
        'branch' => 'main'
    ]));
    $instance->timecreated = time();
    $instance->timemodified = time();
    $DB->insert_record('block_instances', $instance);
    echo "Bloque gitmetrics añadido y configurado en la asignatura.\n";
}

// Matriculamos al usuario admin (id = 2) como profesor para que aparezca en "Mis cursos"
$enrolplugin = enrol_get_plugin('manual');
if ($enrolplugin) {
    $instances = enrol_get_instances($course->id, true);
    $manualinstance = null;
    foreach ($instances as $inst) {
        if ($inst->enrol === 'manual') {
            $manualinstance = $inst;
            break;
        }
    }
    if ($manualinstance) {
        $teacherrole = $DB->get_record('role', ['shortname' => 'editingteacher']);
        if ($teacherrole && !$DB->record_exists('user_enrolments', ['enrolid' => $manualinstance->id, 'userid' => 2])) {
            $enrolplugin->enrol_user($manualinstance, 2, $teacherrole->id);
            echo "Usuario admin matriculado como profesor en 'Panel de Métricas y BdC'.\n";
        }
    }
}

// Calculamos las métricas y las inyectamos como los 4 temas de la asignatura
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/github_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/markdown_parser.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/metrics_calculator.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/renderer.php');

$token      = get_config('block_gitmetrics', 'github_token') ?: '';
$calculator = new \block_gitmetrics\metrics_calculator($token);
$metrics    = $calculator->calculate('https://github.com/julia8873/bdc-prueba', 'main');

global $PAGE;
$PAGE->set_context(context_course::instance($course->id));
$renderer = $PAGE->get_renderer('block_gitmetrics');

// Estilos base de las tarjetas
$styles = '<style>
.gm-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; margin-bottom: 12px; }
.gm-card { display: inline-block; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 14px; margin: 4px; min-width: 130px; }
.gm-card-value { font-size: 20px; font-weight: 700; color: #1e3a8a; }
.gm-card-label { font-size: 11px; color: #475569; }
.gm-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.gm-badge-ok { background: #d1fae5; color: #065f46; }
.gm-tag { display: inline-block; background: #ede9fe; color: #5b21b6; border-radius: 99px; padding: 2px 10px; font-weight: 600; margin: 2px; }
</style>';

$topics = [
    0 => [
        'name' => 'Panel General de Métricas de Base de Conocimiento',
        'summary' => $renderer->render_fullpage_metrics($metrics)
    ],
    1 => [
        'name' => 'Volumen y Tamaño de la Base de Conocimiento',
        'summary' => $styles . $renderer->render_volume($metrics['volume'])
    ],
    2 => [
        'name' => 'Red de Enlaces e Interconectividad Markdown',
        'summary' => $renderer->render_network($metrics['network'])
    ],
    3 => [
        'name' => 'Taxonomía, Metadatos y Etiquetas YAML',
        'summary' => $renderer->render_tags($metrics['tags'])
    ],
    4 => [
        'name' => 'Calidad Markdown y Elementos Estructurales',
        'summary' => $renderer->render_format($metrics['format'])
    ]
];

foreach ($topics as $num => $data) {
    $sec = $DB->get_record('course_sections', ['course' => $course->id, 'section' => $num]);
    if ($sec) {
        $sec->name = $data['name'];
        $sec->summary = $data['summary'];
        $sec->summaryformat = FORMAT_HTML;
        $sec->timemodified = time();
        $DB->update_record('course_sections', $sec);
    } else {
        $sec = new stdClass();
        $sec->course = $course->id;
        $sec->section = $num;
        $sec->name = $data['name'];
        $sec->summary = $data['summary'];
        $sec->summaryformat = FORMAT_HTML;
        $sec->visible = 1;
        $sec->timemodified = time();
        $DB->insert_record('course_sections', $sec);
    }
}
echo "Los 4 temas de la asignatura se han poblado exitosamente con las métricas por categoría.\n";
