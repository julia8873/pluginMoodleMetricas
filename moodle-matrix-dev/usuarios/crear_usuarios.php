<?php
// --8<-- [start:file_desc]
// create_users.php
define('CLI_SCRIPT', true);
require(__DIR__ . '/config.php');
require_once($CFG->dirroot . '/user/lib.php');

$usuarios = [
    ['username' => 'profesor1', 'firstname' => 'Profesor', 'lastname' => 'Simulado', 'email' => 'profesor1@test.local'],
    ['username' => 'alumno1',   'firstname' => 'Alumno',   'lastname' => 'Uno',      'email' => 'alumno1@test.local'],
    ['username' => 'alumno2',   'firstname' => 'Alumno',   'lastname' => 'Dos',      'email' => 'alumno2@test.local'],
];

foreach ($usuarios as $u) {
    $data = new stdClass();
    $data->username  = $u['username'];
    $data->password  = 'Test1234!';
    $data->firstname = $u['firstname'];
    $data->lastname  = $u['lastname'];
    $data->email     = $u['email'];
    $data->auth      = 'manual';
    $data->confirmed = 1;
    $data->mnethostid = $CFG->mnet_localhost_id;

    $id = user_create_user($data, false, false);
    echo "Usuario {$u['username']} creado con id {$id}\n";
}
// --8<-- [end:file_desc]