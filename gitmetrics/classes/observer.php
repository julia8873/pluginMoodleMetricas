<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

class observer {
    public static function course_created(\core\event\course_created $event) {
        $courseid = $event->objectid;
        require_once(__DIR__ . '/matrix_helper.php');
        \block_gitmetrics\matrix_helper::ensure_room_and_bot((int)$courseid);
        
        // Aprovisionar repositorio para la asignatura y dar acceso al creador
        self::provision_course_repo($courseid, $event->userid);
    }

    // --8<-- [start:teacher_assigned]
    public static function teacher_assigned(\core\event\role_assigned $event) {
        global $DB;

        $context = $event->get_context();
        if ($context->contextlevel != CONTEXT_COURSE) {
            return;
        }

        $role_assignment = $DB->get_record('role_assignments', ['id' => $event->objectid]);
        if (!$role_assignment) {
            return;
        }

        $role = $DB->get_record('role', ['id' => $role_assignment->roleid]);
        if (!$role || $role->shortname !== 'editingteacher') {
            return;
        }

        self::provision_course_repo($context->instanceid, $event->relateduserid);
    }

    public static function provision_course_repo($course_id, $userid) {
        global $DB, $CFG;

        $course = $DB->get_record('course', ['id' => $course_id]);
        $user = $DB->get_record('user', ['id' => $userid]);
        
        if (!$course || !$user) {
            return;
        }

        $template_owner = get_config('block_gitmetrics', 'template_owner');
        $template_repo = get_config('block_gitmetrics', 'template_repo');
        $template_provider = get_config('block_gitmetrics', 'template_provider');
        $target_namespace = get_config('block_gitmetrics', 'target_namespace');

        if (empty($template_provider)) {
            $template_provider = 'github'; // fallback
        }
        
        if (empty($target_namespace)) {
            $target_namespace = $template_owner; // default fallback if empty
        }

        $token = get_config('block_gitmetrics', $template_provider . '_token');
        if (empty($token) || empty($template_owner) || empty($template_repo)) {
            return; // Configuración incompleta
        }

        require_once(__DIR__ . '/metrics_calculator.php');
        try {
            $client = \block_gitmetrics\metrics_calculator::make_client($template_provider, $token);
        } catch (\Exception $e) {
            return;
        }

        $course_repo_record = $DB->get_record('block_gitmetrics_course_repo', ['course_id' => $course_id]);
        $safe_course_name = preg_replace('/[^a-zA-Z0-9_-]/', '-', strtolower($course->shortname));
        $new_repo_name = 'bdc-' . $safe_course_name;

        if (!$course_repo_record) {
            $record = new \stdClass();
            $record->course_id = $course_id;
            $record->provider = $template_provider;
            $record->status = 'pendiente';
            $record->repo_url = '';
            $record->timecreated = time();
            $record->id = $DB->insert_record('block_gitmetrics_course_repo', $record);

            try {
                $html_url = $client->create_repo_from_template($template_owner, $template_repo, $target_namespace, $new_repo_name);
                
                $record->status = 'creado';
                $record->repo_url = $html_url;
                $record->error_msg = null;
                $DB->update_record('block_gitmetrics_course_repo', $record);
                
                $course_repo_record = $record;
            } catch (\Exception $e) {
                $record->status = 'error';
                $record->error_msg = $e->getMessage();
                $DB->update_record('block_gitmetrics_course_repo', $record);
                return;
            }
        }

        if ($course_repo_record && $course_repo_record->status === 'creado') {
            try {
                $client->add_collaborator($target_namespace, $new_repo_name, $user->username, 'maintainer');
            } catch (\Exception $e) {
            }
        }
    }
    // --8<-- [start:student_enrolled]
    public static function student_enrolled(\core\event\role_assigned $event) {
        global $DB;

        $role = $DB->get_record('role', ['id' => $event->objectid]);
        if (!$role || $role->shortname !== 'student') {
            return;
        }

        if ($event->contextlevel != CONTEXT_COURSE) {
            return;
        }

        self::provision_student_fork($event->contextinstanceid, $event->relateduserid);
    }

    public static function provision_student_fork($course_id, $userid) {
        global $DB;

        $course = $DB->get_record('course', ['id' => $course_id]);
        $user = $DB->get_record('user', ['id' => $userid]);
        if (!$course || !$user) {
            return;
        }

        $course_repo_record = $DB->get_record('block_gitmetrics_course_repo', ['course_id' => $course->id]);
        $student_fork_record = $DB->get_record('block_gitmetrics_student_fork', ['course_id' => $course->id, 'userid' => $user->id]);

        if (!$student_fork_record) {
            $student_fork_record = new \stdClass();
            $student_fork_record->course_id = $course->id;
            $student_fork_record->userid = $user->id;
            $student_fork_record->id_pseudo = \core\uuid::generate();
            $student_fork_record->status = 'pendiente';
            $student_fork_record->timecreated = time();
            $student_fork_record->id = $DB->insert_record('block_gitmetrics_student_fork', $student_fork_record);
        }

        if (!$course_repo_record || $course_repo_record->status !== 'creado') {
            return;
        }

        if ($student_fork_record->status === 'creado') {
            return;
        }

        $provider = get_config('block_gitmetrics', 'template_provider') ?: 'github';
        $token = get_config('block_gitmetrics', 'github_token');
        if (empty($token)) {
            return;
        }

        $target_namespace = get_config('block_gitmetrics', 'target_namespace');
        if (empty($target_namespace)) {
            return;
        }

        require_once(__DIR__ . '/metrics_calculator.php');
        try {
            $client = \block_gitmetrics\metrics_calculator::make_client($provider, $token);
        } catch (\Exception $e) {
            return;
        }

        $parsed = parse_url($course_repo_record->repo_url, PHP_URL_PATH);
        $parts = explode('/', trim($parsed, '/'));
        if (count($parts) < 2) {
            return;
        }
        $source_owner = $parts[0];
        $source_repo = $parts[1];

        $safe_course_name = preg_replace('/[^a-zA-Z0-9_-]/', '-', strtolower($course->shortname));
        $new_fork_name = 'bdc-' . $safe_course_name . '-' . $student_fork_record->id_pseudo;

        try {
            $fork_url = $client->fork_repo($source_owner, $source_repo, $target_namespace, $new_fork_name);
            
            $student_fork_record->fork_url = $fork_url;
            $student_fork_record->status = 'creado';
            $student_fork_record->error_msg = null;
            $DB->update_record('block_gitmetrics_student_fork', $student_fork_record);
            
            // Notificar a Matrix del fork del estudiante para que el bot lo conozca
            require_once(__DIR__ . '/matrix_helper.php');
            \block_gitmetrics\matrix_helper::send_student_fork_state($course_id, $userid, $fork_url);
        } catch (\Exception $e) {
            $student_fork_record->status = 'error';
            $student_fork_record->error_msg = $e->getMessage();
            $DB->update_record('block_gitmetrics_student_fork', $student_fork_record);
        }
    }
    // --8<-- [end:student_enrolled]
}
