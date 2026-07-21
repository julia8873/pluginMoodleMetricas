<?php
// ─────────────────────────────────────────────────────────────────────────────
// db/tasks.php
// Definicion de tareas programadas (Scheduled Tasks) de block_gitmetrics.
// ─────────────────────────────────────────────────────────────────────────────

defined('MOODLE_INTERNAL') || die();

$tasks = [
    // OBSIDIAN_OPTIONAL_START
    // Tarea para sincronizar automaticamente el vault de Obsidian cada hora.
    // Para eliminar la integracion con Obsidian, borra este bloque.
    [
        'classname' => 'block_gitmetrics\task\sync_obsidian',
        'blocking'  => 0,
        'minute'    => '*',
        'hour'      => '*',
        'day'       => '*',
        'dayofweek' => '*',
        'month'     => '*'
    ],
    // OBSIDIAN_OPTIONAL_END
];
