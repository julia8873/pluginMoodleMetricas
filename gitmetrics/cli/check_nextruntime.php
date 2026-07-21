<?php
define('CLI_SCRIPT', true);
require('/bitnami/moodle/config.php');
global $DB;
$t = $DB->get_record('task_scheduled', ['classname' => '\block_gitmetrics\task\sync_obsidian']);
if ($t) {
    echo "Last run: " . date('Y-m-d H:i:s', $t->lastruntime) . "\n";
    echo "Next run: " . date('Y-m-d H:i:s', $t->nextruntime) . "\n";
    echo "Minute schedule: " . $t->minute . "\n";
    echo "Hour schedule: " . $t->hour . "\n";
} else {
    echo "Task sync_obsidian not found in task_scheduled table.\n";
}
