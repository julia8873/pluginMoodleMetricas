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
