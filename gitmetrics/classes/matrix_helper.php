<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

class matrix_helper {

    /**
     * Asegura que el curso especificado tenga una sala de Matrix creada en Synapse
     * y que el bot (@githubbot:localhost) este invitado y unido a dicha sala.
     *
     * @param int $courseid ID del curso de Moodle
     * @param string|null $roomname Nombre opcional para la sala de Matrix
     * @return bool True si la sala y el bot estan configurados/unidos con exito.
     */
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

        $botuserid = '@githubbot:localhost';
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

        return true;
    }

    /**
     * Asegura que el cliente (@githubbot:localhost) y la instancia del plugin
     * dev.julia.githubbot esten registrados, activos y online en Maubot.
     */
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
                if (!empty($inst['id']) && $inst['id'] === 'dev.julia.githubbot' && !empty($inst['started'])) {
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
            'username' => 'githubbot',
            'password' => 'botpass123'
        ]));
        curl_setopt($ch, CURLOPT_HTTPHEADER, [$authheader, 'Content-Type: application/json', 'Timeout: 6']);
        curl_exec($ch);
        curl_close($ch);

        // 2. Crear o arrancar la instancia dev.julia.githubbot
        $ch = curl_init("{$mauboturl}/instance/dev.julia.githubbot");
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PUT');
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
            'type' => 'dev.julia.githubbot',
            'primary_user' => '@githubbot:localhost',
            'enabled' => true,
            'config' => ''
        ]));
        curl_setopt($ch, CURLOPT_HTTPHEADER, [$authheader, 'Content-Type: application/json', 'Timeout: 6']);
        curl_exec($ch);
        curl_close($ch);
    }

    /**
     * Aplica la creacion de sala y union de bot para todos los cursos existentes.
     *
     * @return int Numero de cursos procesados
     */
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
}
