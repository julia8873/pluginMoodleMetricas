<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

class observer {

    /**
     * Observador para el evento de creacion de un curso (\core\event\course_created).
     * Crea automaticamente la sala de chat en Matrix e invita/une al bot @githubbot:localhost.
     *
     * @param \core\event\course_created $event
     */
    public static function course_created(\core\event\course_created $event) {
        $courseid = (int)$event->objectid;
        if ($courseid > 1) {
            matrix_helper::ensure_room_and_bot($courseid);
        }
    }
}
