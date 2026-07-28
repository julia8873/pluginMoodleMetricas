<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

/*
--8<-- [start:class_desc]
Helper para la integración de Matrix en Moodle.

Gestiona la creación automática de salas en el servidor Synapse
para cada curso, y orquesta la invitación y unión del bot (@llmwikiassistant)
a dichas salas mediante llamadas a las APIs REST de Synapse y Maubot.
--8<-- [end:class_desc]
*/
class matrix_helper {

    /**
     * Asegura que el curso especificado tenga una sala de Matrix creada en Synapse
     * y que el bot (@llmwikiassistant:localhost) este invitado y unido a dicha sala.
     *
     * @param int $courseid ID del curso de Moodle
     * @param string|null $roomname Nombre opcional para la sala de Matrix
     * @return bool True si la sala y el bot estan configurados/unidos con exito.
     */
    // --8<-- [start:ensure_room_and_bot]
    public static function ensure_room_and_bot(int $courseid, ?string $roomname = null): bool {
        global $DB, $CFG;

        if ($courseid <= 1) {
            return false;
        }

        $course = $DB->get_record('course', ['id' => $courseid]);
        if (!$course) {
            return false;
        }

        if (empty(get_config('core', 'enablecommunicationsubsystem'))) {
            set_config('enablecommunicationsubsystem', 1);
        }

        $allowedports = get_config('core', 'curlsecurityallowedport');
        if (empty($allowedports) || !str_contains($allowedports, '8008') || !str_contains($allowedports, '29316')) {
            set_config('curlsecurityallowedport', "443\n80\n8008\n8081\n8080\n29316");
        }

        $token = get_config('communication_matrix', 'matrixaccesstoken');
        if (empty($token)) {
            $synapseurl = get_config('communication_matrix', 'matrixhomeserverurl') ?: 'http://matrix-synapse:8008';
            $ch = curl_init("{$synapseurl}/_matrix/client/v3/login");
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
                'type' => 'm.login.password',
                'user' => 'admin',
                'password' => 'adminpass123'
            ]));
            curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json', 'Timeout: 5']);
            $res = curl_exec($ch);
            curl_close($ch);
            if ($res) {
                $data = json_decode($res, true);
                if (!empty($data['access_token'])) {
                    $token = $data['access_token'];
                    set_config('matrixhomeserverurl', 'http://matrix-synapse:8008', 'communication_matrix');
                    set_config('matrixaccesstoken', $token, 'communication_matrix');
                    set_config('matrixelementurl', 'http://localhost:8081', 'communication_matrix');
                }
            }
        }

        if (empty($token)) {
            return false;
        }

        self::ensure_maubot_active();

        $context = \core\context\course::instance($course->id);
        $commrecord = $DB->get_record('communication', [
            'contextid' => $context->id,
            'component' => 'core_course',
            'instancetype' => 'coursecommunication',
            'instanceid' => $course->id
        ]);

        $defaultname = $roomname ?: ("Chat " . ($course->shortname ?: $course->fullname));

        if (!$commrecord) {
            $commrecord = new \stdClass();
            $commrecord->contextid = $context->id;
            $commrecord->component = 'core_course';
            $commrecord->instancetype = 'coursecommunication';
            $commrecord->instanceid = $course->id;
            $commrecord->provider = 'communication_matrix';
            $commrecord->roomname = $defaultname;
            $commrecord->active = 1;
            $commrecord->timecreated = time();
            $commrecord->timemodified = time();
            $commrecord->id = $DB->insert_record('communication', $commrecord);
        } else {
            $update = false;
            if ($commrecord->provider !== 'communication_matrix') {
                $commrecord->provider = 'communication_matrix';
                $update = true;
            }
            if (empty($commrecord->roomname)) {
                $commrecord->roomname = $defaultname;
                $update = true;
            }
            if ($commrecord->active != 1) {
                $commrecord->active = 1;
                $update = true;
            }
            if ($update) {
                $commrecord->timemodified = time();
                $DB->update_record('communication', $commrecord);
            }
        }

        require_once($CFG->dirroot . '/communication/classes/api.php');
        $comm = \core_communication\api::load_by_instance(
            context: $context,
            component: 'core_course',
            instancetype: 'coursecommunication',
            instanceid: $course->id,
            provider: 'communication_matrix'
        );

        $processor = $comm->get_processor();
        if ($processor) {
            if (class_exists('\communication_matrix\matrix_room')) {
                $existingroom = \communication_matrix\matrix_room::load_by_processor_id($processor->get_id());
                if (!$existingroom) {
                    \communication_matrix\matrix_room::create_room_record(
                        processorid: $processor->get_id(),
                        topic: 'Chat del curso ' . $course->fullname
                    );
                }
            }
        }

        $provider = $processor ? $processor->get_room_provider() : null;
        $roomid = '';
        if ($provider) {
            try {
                $provider->create_chat_room();
            } catch (\Exception $e) {
                // Ignorar si ya existia la sala en Synapse
            }
        }

        $matrixroom = $DB->get_record('matrix_room', ['commid' => $commrecord->id]);
        if ($matrixroom && !empty($matrixroom->roomid)) {
            $roomid = $matrixroom->roomid;
        }

        if (empty($roomid)) {
            return false;
        }

        $botuserid = '@llmwikiassistant:localhost';
        $synapseurl = get_config('communication_matrix', 'matrixhomeserverurl') ?: 'http://matrix-synapse:8008';

        $ch = curl_init("{$synapseurl}/_matrix/client/v3/rooms/" . urlencode($roomid) . "/invite");
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            "Authorization: Bearer " . $token,
            "Content-Type: application/json"
        ]);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(['user_id' => $botuserid]));
        curl_exec($ch);
        curl_close($ch);

        $ch = curl_init("{$synapseurl}/_synapse/admin/v1/join/" . urlencode($roomid));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            "Authorization: Bearer " . $token,
            "Content-Type: application/json"
        ]);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(['user_id' => $botuserid]));
        curl_exec($ch);
        curl_close($ch);

        // Escribir state event es.ugr.gitmetrics.course_link
        $stateurl = "{$synapseurl}/_matrix/client/v3/rooms/" . urlencode($roomid) . "/state/es.ugr.gitmetrics.course_link/";
        $ch = curl_init($stateurl);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            "Authorization: Bearer " . $token,
            "Content-Type: application/json"
        ]);
        $res = curl_exec($ch);
        $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $write_state = true;
        if ($httpcode == 200 && $res) {
            $data = json_decode($res, true);
            if (isset($data['course_id'])) {
                if ($data['course_id'] != $courseid) {
                    error_log("matrix_helper::ensure_room_and_bot - Error de idempotencia: sala {$roomid} ya tiene course_id {$data['course_id']}, se esperaba {$courseid}");
                }
                $write_state = false;
            }
        }

        if ($write_state) {
            $ch = curl_init($stateurl);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT");
            curl_setopt($ch, CURLOPT_HTTPHEADER, [
                "Authorization: Bearer " . $token,
                "Content-Type: application/json"
            ]);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(['course_id' => $courseid]));
            curl_exec($ch);
            curl_close($ch);
        }

        return true;
    }
    // --8<-- [end:ensure_room_and_bot]

    /**
     * Envia el state event `es.ugr.gitmetrics.student_fork` a la sala del curso en Matrix
     * con la URL del repositorio personal del estudiante (su state_key es el @usuario:dominio).
     */
    public static function send_student_fork_state(int $courseid, int $userid, string $fork_url): bool {
        global $DB, $CFG;

        if ($courseid <= 1) {
            return false;
        }

        require_once($CFG->dirroot . '/communication/classes/api.php');
        $context = \context_course::instance($courseid);
        $communication = \core_communication\api::load_by_instance($context, 'core_course', 'coursecommunication', $courseid);
        if (!$communication) {
            return false;
        }

        $processor = $communication->get_processor();
        if (!$processor) {
            return false;
        }

        if (class_exists('\communication_matrix\matrix_room')) {
            $existingroom = \communication_matrix\matrix_room::load_by_processor_id($processor->get_id());
            if ($existingroom && !empty($existingroom->get_room_id())) {
                $roomid = $existingroom->get_room_id();
            } else {
                return false;
            }
        } else {
            return false;
        }

        $user = $DB->get_record('user', ['id' => $userid]);
        if (!$user) {
            return false;
        }

        $token = get_config('communication_matrix', 'matrixaccesstoken');
        $synapseurl = get_config('communication_matrix', 'matrixhomeserverurl') ?: 'http://matrix-synapse:8008';
        if (empty($token) || empty($synapseurl)) {
            return false;
        }

        $domain = get_config('communication_matrix', 'matrixdomain');
        if (empty($domain)) {
            $domain = 'localhost'; // El server_name configurado en homeserver.yaml de Synapse
        }
        $matrix_user_id = '@' . strtolower($user->username) . ':' . $domain;

        $state_key = "moodle_" . $userid;
        $stateurl = "{$synapseurl}/_matrix/client/v3/rooms/" . urlencode($roomid) . "/state/es.ugr.gitmetrics.student_fork/" . urlencode($state_key);
        $ch = curl_init($stateurl);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT");
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            "Authorization: Bearer " . $token,
            "Content-Type: application/json"
        ]);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
            'fork_url' => $fork_url,
            'matrix_user_id' => $matrix_user_id
        ]));
        $res = curl_exec($ch);
        $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        return ($httpcode == 200);
    }

    /**
     * Asegura que el cliente (@llmwikiassistant:localhost) y la instancia del plugin
     * dev.julia.llmwikiassistant esten registrados, activos y online en Maubot.
     */
    // --8<-- [start:ensure_maubot_active]
    public static function ensure_maubot_active(): void {
        $mauboturl = 'http://maubot:29316/_matrix/maubot/v1';
        $ch = curl_init("{$mauboturl}/auth/login");
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
            'username' => 'admin',
            'password' => 'adminpass123'
        ]));
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json', 'Timeout: 4']);
        $res = curl_exec($ch);
        curl_close($ch);

        if (!$res) {
            return;
        }

        $data = json_decode($res, true);
        if (empty($data['token'])) {
            return;
        }

        $authheader = "Authorization: Bearer " . $data['token'];

        $ch = curl_init("{$mauboturl}/instances");
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [$authheader, 'Timeout: 4']);
        $res = curl_exec($ch);
        curl_close($ch);

        $need_setup = true;
        if ($res && ($instances = json_decode($res, true)) && is_array($instances)) {
            foreach ($instances as $inst) {
                if (!empty($inst['id']) && $inst['id'] === 'dev.julia.llmwikiassistant' && !empty($inst['started'])) {
                    $need_setup = false;
                    break;
                }
            }
        }

        if (!$need_setup) {
            return;
        }

        // 1. Registrar o actualizar cliente en Maubot
        $ch = curl_init("{$mauboturl}/client/auth/local/login?update_client=true");
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
            'username' => 'llmwikiassistant',
            'password' => 'botpass123'
        ]));
        curl_setopt($ch, CURLOPT_HTTPHEADER, [$authheader, 'Content-Type: application/json', 'Timeout: 6']);
        curl_exec($ch);
        curl_close($ch);

        // 2. Crear o arrancar la instancia dev.julia.llmwikiassistant
        $ch = curl_init("{$mauboturl}/instance/dev.julia.llmwikiassistant");
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PUT');
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
            'type' => 'dev.julia.llmwikiassistant',
            'primary_user' => '@llmwikiassistant:localhost',
            'enabled' => true,
            'config' => ''
        ]));
        curl_setopt($ch, CURLOPT_HTTPHEADER, [$authheader, 'Content-Type: application/json', 'Timeout: 6']);
        curl_exec($ch);
        curl_close($ch);
    }
    // --8<-- [end:ensure_maubot_active]

    /**
     * Aplica la creacion de sala y union de bot para todos los cursos existentes.
     *
     * @return int Numero de cursos procesados
     */
    // --8<-- [start:process_all_existing_courses]
    public static function process_all_existing_courses(): int {
        global $DB;
        $courses = $DB->get_records_select('course', 'id > 1');
        $count = 0;
        foreach ($courses as $c) {
            if (self::ensure_room_and_bot((int)$c->id)) {
                $count++;
            }
        }
        return $count;
    }
    // --8<-- [end:process_all_existing_courses]
}
