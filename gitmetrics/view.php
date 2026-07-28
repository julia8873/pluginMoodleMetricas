<?php
/*
--8<-- [start:file_desc]
Pagina completa de visualizacion de metricas de la Base de Conocimiento Git.
Soporta GitHub, GitLab OSL y GitLab local. Se ejecuta en un layout 'report'.
--8<-- [end:file_desc]
*/

require_once(__DIR__ . '/../../config.php');

$courseid = optional_param('courseid', SITEID, PARAM_INT);
$blockid  = optional_param('blockid', 0, PARAM_INT);

$course = $DB->get_record('course', ['id' => $courseid], '*', MUST_EXIST);
require_login($course);

$PAGE->set_url('/blocks/gitmetrics/view.php', ['courseid' => $courseid, 'blockid' => $blockid]);
$PAGE->set_title(get_string('pluginname', 'block_gitmetrics'));
$PAGE->set_heading($course->fullname);
$PAGE->set_pagelayout('report');

// -- Manejo de acciones (ej. reintentar aprovisionamiento) ----------------
$action = optional_param('action', '', PARAM_ALPHA);
if ($action === 'retry_fork' && has_capability('moodle/course:update', context_course::instance($courseid))) {
    require_sesskey();
    $userid = required_param('userid', PARAM_INT);
    require_once(__DIR__ . '/classes/observer.php');
    \block_gitmetrics\observer::provision_student_fork($courseid, $userid);
    redirect(new moodle_url('/blocks/gitmetrics/view.php', ['courseid' => $courseid, 'blockid' => $blockid]));
}

// -- Leer configuracion de la instancia del bloque -------------------------
$repourl  = optional_param('repo_url', '', PARAM_RAW);
$branch   = optional_param('branch', 'main', PARAM_TEXT);
$provider = '';

if ($blockid > 0 && ($instance = $DB->get_record('block_instances', ['id' => $blockid]))) {
    if (!empty($instance->configdata)) {
        $config = unserialize(base64_decode($instance->configdata));

        // Nuevo campo unificado: config_repo_url
        if (!empty($config->repo_url)) {
            $repourl  = empty($repourl) ? trim($config->repo_url) : $repourl;
        }
        // Retrocompatibilidad: campo antiguo config_github_url
        if (empty($repourl) && !empty($config->github_url)) {
            $repourl = trim($config->github_url);
        }
        if (!empty($config->branch)) {
            $branch = trim($config->branch);
        }
        if (!empty($config->provider)) {
            $provider = trim($config->provider);
        }
    }
}

// -- Si se abrio desde la pestana del curso (blockid = 0), buscar en el curso -
if (empty($repourl)) {
    $context   = context_course::instance($courseid);
    $instances = $DB->get_records('block_instances', ['blockname' => 'gitmetrics', 'parentcontextid' => $context->id]);
    foreach ($instances as $inst) {
        if (!empty($inst->configdata)) {
            $config = unserialize(base64_decode($inst->configdata));
            $url = $config->repo_url ?? $config->github_url ?? '';
            if (!empty($url)) {
                $repourl  = trim($url);
                $provider = $config->provider ?? '';
                if (!empty($config->branch)) {
                    $branch = trim($config->branch);
                }
                break;
            }
        }
    }
}

// -- Fallback: Buscar en la base de datos de aprovisionamiento de repositorios de curso --
if (empty($repourl)) {
    $course_repo = $DB->get_record('block_gitmetrics_course_repo', ['course_id' => $courseid]);
    if ($course_repo && !empty($course_repo->repo_url)) {
        $repourl = $course_repo->repo_url;
        $provider = $course_repo->provider;
        $branch = 'main'; // default
    }
}

// -- Repositorio por defecto si no se ha configurado ninguno --------------
if (empty($repourl)) {
    // Si no se encuentra un repositorio, no forzamos uno ficticio, simplemente lo dejamos vacío.
    $repourl = '';
}

// -- Determinar proveedor -------------------------------------------------
// Prioridad: configuracion del bloque > ajuste global > auto-deteccion por URL
if (empty($provider)) {
    $provider = get_config('block_gitmetrics', 'default_provider') ?: 'github';
}

// Token y URL de GitLab segun el proveedor
if (str_contains($repourl, 'github.com')) {
    $token      = get_config('block_gitmetrics', 'github_token') ?: '';
    $gitlab_url = 'https://gitlab.com';
    $provider   = 'github';
} elseif ($provider === 'gitlab' || str_contains($repourl, 'gitlab')) {
    $token      = get_config('block_gitmetrics', 'gitlab_token') ?: '';
    $gitlab_url = get_config('block_gitmetrics', 'gitlab_url') ?: 'https://gitlab.com';
    $provider   = 'gitlab';
} else {
    $token      = get_config('block_gitmetrics', 'github_token') ?: '';
    $gitlab_url = 'https://gitlab.com';
}

// --8<-- [start:view_logic]
echo $OUTPUT->header();

if (empty($repourl)) {
    echo $OUTPUT->notification('No hay un repositorio configurado para este curso. Por favor, añade el bloque de GitMetrics o asegúrate de que el curso está aprovisionado correctamente.', 'info');
} else {
    $cache   = new \block_gitmetrics\metrics_cache($DB);
    $metrics = $cache->get($repourl, $blockid);

    if ($metrics === null) {
        try {
            $calculator = new \block_gitmetrics\metrics_calculator($token, $provider, $gitlab_url);
            $metrics    = $calculator->calculate($repourl, $branch);
            $cache->set($repourl, $blockid, $metrics);
        } catch (\Exception $e) {
            echo $OUTPUT->notification('Error al cargar métricas: ' . $e->getMessage(), 'error');
            $metrics = null;
        }
    }

    if ($metrics !== null) {
        $renderer = $PAGE->get_renderer('block_gitmetrics');
        echo '<div class="container-fluid" style="max-width: 1300px; margin: 0 auto; padding: 20px 0;">';
        echo $renderer->render_fullpage_metrics($metrics);

        // Mostrar panel de gestión si es profesor
        $context = context_course::instance($courseid);
        if (has_capability('moodle/course:update', $context)) {
            $progress_api = new \block_gitmetrics\student_progress($DB);
            $management_data = $progress_api->get_management_data($courseid, $blockid);
            echo $renderer->render_management_panel($management_data);
        }
        echo '</div>';
    }
}

echo $OUTPUT->footer();
// --8<-- [end:view_logic]
