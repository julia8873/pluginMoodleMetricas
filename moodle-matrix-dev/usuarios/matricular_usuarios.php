<?php
define('CLI_SCRIPT', true);
require(__DIR__ . '/config.php');
require_once($CFG->dirroot . '/enrol/manual/locallib.php');

$course = $DB->get_record('course', ['shortname' => 'AA'], '*', MUST_EXIST);
$context = context_course::instance($course->id);
$enrol = enrol_get_plugin('manual');
$instance = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual'], '*', MUST_EXIST);

$mapa = [
    'profesor1' => 'editingteacher',
    'alumno1'   => 'student',
    'alumno2'   => 'student',
];

foreach ($mapa as $username => $rolshortname) {
    $user = $DB->get_record('user', ['username' => $username], '*', MUST_EXIST);
    $role = $DB->get_record('role', ['shortname' => $rolshortname], '*', MUST_EXIST);
    $enrol->enrol_user($instance, $user->id, $role->id);
    echo "{$username} matriculado como {$rolshortname}\n";
}