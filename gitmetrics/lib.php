<?php
// -----------------------------------------------------------------------------
// Funciones de biblioteca para block_gitmetrics (Integración con el curso)
// -----------------------------------------------------------------------------

defined('MOODLE_INTERNAL') || die();

/*
--8<-- [start:file_desc]
Funciones de biblioteca para block_gitmetrics (Integración con el curso).
Añade una pestaña en la navegación secundaria superior de la asignatura (curso)
para acceder directamente a la página completa de Métricas Git.
--8<-- [end:file_desc]
*/
// --8<-- [start:block_gitmetrics_extend_navigation_course]
function block_gitmetrics_extend_navigation_course(navigation_node $coursenode, stdClass $course, context $context) {
    if (!has_capability('moodle/course:view', $context)) {
        return;
    }

    $url = new moodle_url('/blocks/gitmetrics/view.php', ['courseid' => $course->id]);
    $node = $coursenode->add(
        get_string('pluginname', 'block_gitmetrics'),
        $url,
        navigation_node::TYPE_SETTING,
        null,
        'gitmetrics',
        new pix_icon('i/report', '')
    );
    $node->showinflatnavigation = true;
}
// --8<-- [end:block_gitmetrics_extend_navigation_course]
