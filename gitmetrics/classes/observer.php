<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

class observer {
    public static function course_created(\core\event\course_created $event) {
        $courseid = $event->objectid;
        require_once(__DIR__ . '/matrix_helper.php');
        \block_gitmetrics\matrix_helper::ensure_room_and_bot((int)$courseid);
    }
}
