<?php
define('CLI_SCRIPT', true);
require('/bitnami/moodle/config.php');
require_once('/bitnami/moodle/blocks/gitmetrics/classes/matrix_helper.php');
global $DB;
$f = $DB->get_record('block_gitmetrics_student_fork', ['course_id' => 7, 'userid' => 6]);
if ($f) {
    global $CFG;
    $context = \context_course::instance(7);
    $communication = \core_communication\api::load_by_instance($context, 'core_course', 'coursecommunication', 7);
    $processor = $communication->get_processor();
    $existingroom = \communication_matrix\matrix_room::load_by_processor_id($processor->get_id());
    $roomid = $existingroom->get_room_id();
    $token = get_config('communication_matrix', 'matrixaccesstoken');
    $synapseurl = get_config('communication_matrix', 'matrixhomeserverurl') ?: 'http://matrix-synapse:8008';
    $matrix_user_id = '@student1:localhost';
    
    // CHANGE HERE: use moodle_userid instead of matrix_user_id as the state key
    $stateurl = "{$synapseurl}/_matrix/client/v3/rooms/" . urlencode($roomid) . "/state/es.ugr.gitmetrics.student_fork/" . urlencode("moodle_6");
    $ch = curl_init($stateurl);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT");
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "Authorization: Bearer " . $token,
        "Content-Type: application/json"
    ]);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(['fork_url' => $f->fork_url, 'matrix_user_id' => $matrix_user_id]));
    $res = curl_exec($ch);
    $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    echo "HTTP $httpcode - Res: $res\n";
} else {
    echo "Fork not found.\n";
}
