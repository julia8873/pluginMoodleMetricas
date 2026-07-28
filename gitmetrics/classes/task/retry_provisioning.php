<?php
namespace block_gitmetrics\task;

defined('MOODLE_INTERNAL') || die();

/*
--8<-- [start:class_desc]
Tarea programada para reintentar la creación de repositorios de curso y forks de estudiantes que se quedaron en estado pendiente o en error.
--8<-- [end:class_desc]
*/
class retry_provisioning extends \core\task\scheduled_task {
    // --8<-- [start:get_name]
    public function get_name() {
        // En un plugin real idealmente iría en lang/en/block_gitmetrics.php
        return 'Reintentar aprovisionamiento de repositorios y forks (GitMetrics)';
    }
    // --8<-- [end:get_name]

    // --8<-- [start:execute]
    public function execute() {
        global $DB;
        mtrace("Iniciando tarea de reintento de aprovisionamiento GitMetrics...");

        require_once(__DIR__ . '/../../classes/observer.php');

        // 1. Reintentar repositorios de curso
        $pending_repos = $DB->get_records_select('block_gitmetrics_course_repo', "(status = 'pendiente' OR status = 'error') AND attempts < 5");
        if ($pending_repos) {
            foreach ($pending_repos as $repo) {
                mtrace("Reintentando repo del curso ID: {$repo->course_id} (Intento: " . ($repo->attempts + 1) . ")");
                $repo->attempts++;
                $DB->update_record('block_gitmetrics_course_repo', $repo);
                
                // Necesitamos un profesor para pasarlo al aprovisionador
                $context = \context_course::instance($repo->course_id);
                $teachers = get_enrolled_users($context, 'moodle/course:update');
                $teacher = reset($teachers);
                $teacher_id = $teacher ? $teacher->id : null;
                
                if ($teacher_id) {
                    \block_gitmetrics\observer::provision_course_repo($repo->course_id, $teacher_id);
                } else {
                    mtrace("  -> No hay profesores para asignar como colaboradores, pero se intentará crear.");
                    // Fallback con admin u omitir añadir colaborador
                    $admin = $DB->get_record('user', ['username' => 'admin']);
                    if ($admin) {
                        \block_gitmetrics\observer::provision_course_repo($repo->course_id, $admin->id);
                    }
                }
            }
        } else {
            mtrace("No hay repositorios de curso pendientes para reintentar (o excedieron los 5 intentos).");
        }

        // 2. Reintentar forks de alumnos
        $pending_forks = $DB->get_records_select('block_gitmetrics_student_fork', "(status = 'pendiente' OR status = 'error') AND attempts < 5");
        if ($pending_forks) {
            foreach ($pending_forks as $fork) {
                mtrace("Reintentando fork ID: {$fork->id} (Curso: {$fork->course_id}, Usuario: {$fork->userid}, Intento: " . ($fork->attempts + 1) . ")");
                
                $fork->attempts++;
                $DB->update_record('block_gitmetrics_student_fork', $fork);

                \block_gitmetrics\observer::provision_student_fork($fork->course_id, $fork->userid);
            }
        } else {
            mtrace("No hay forks de estudiantes pendientes para reintentar (o excedieron los 5 intentos).");
        }
    }
    // --8<-- [end:execute]
}
