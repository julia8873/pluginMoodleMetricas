<?php
define('CLI_SCRIPT', true);
require('/bitnami/moodle/config.php');
global $DB;

$task = $DB->get_record('task_scheduled', ['classname' => '\block_gitmetrics\task\sync_obsidian']);
if ($task) {
    $task->minute = '*';
    $task->hour = '*';
    $task->nextruntime = time() - 10;
    $DB->update_record('task_scheduled', $task);
    echo "Sincronización de Obsidian configurada para ejecutarse AUTOMÁTICAMENTE en cada minuto de cron.\n";
} else {
    echo "No se encontró la tarea en task_scheduled, intentando registrarla...\n";
    $newtask = new \stdClass();
    $newtask->component = 'block_gitmetrics';
    $newtask->classname = '\block_gitmetrics\task\sync_obsidian';
    $newtask->lastruntime = 0;
    $newtask->nextruntime = time() - 10;
    $newtask->blocking = 0;
    $newtask->minute = '*';
    $newtask->hour = '*';
    $newtask->day = '*';
    $newtask->month = '*';
    $newtask->dayofweek = '*';
    $newtask->faildelay = 0;
    $newtask->customised = 0;
    $newtask->disabled = 0;
    $DB->insert_record('task_scheduled', $newtask);
    echo "Tarea sync_obsidian registrada exitosamente para ejecución minuto a minuto.\n";
}
