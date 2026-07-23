<?php
defined('MOODLE_INTERNAL') || die();

// -- Permisos del plugin block_gitmetrics ---------------------------------

$capabilities = [

    // Quién puede añadir este bloque a un curso
    'block/gitmetrics:addinstance' => [
        'riskbitmask' => RISK_SPAM,
        'captype'     => 'write',
        'contextlevel' => CONTEXT_BLOCK,
        'archetypes'  => [
            'editingteacher' => CAP_ALLOW,
            'manager'        => CAP_ALLOW,
        ],
        'clonepermissionsfrom' => 'moodle/site:manageblocks',
    ],

    // Quién puede añadirlo en "Mi Moodle"
    'block/gitmetrics:myaddinstance' => [
        'captype'      => 'write',
        'contextlevel' => CONTEXT_SYSTEM,
        'archetypes'   => [
            'user' => CAP_ALLOW,
        ],
        'clonepermissionsfrom' => 'moodle/my:manageblocks',
    ],

    // Quién puede ver las métricas del bloque
    'block/gitmetrics:viewmetrics' => [
        'captype'      => 'read',
        'contextlevel' => CONTEXT_BLOCK,
        'archetypes'   => [
            'student'        => CAP_ALLOW,
            'editingteacher' => CAP_ALLOW,
            'manager'        => CAP_ALLOW,
        ],
    ],
];