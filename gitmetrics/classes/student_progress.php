<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

/*
--8<-- [start:class_desc]
Puente hacia el endpoint HTTP nativo del plugin Maubot para mostrar el
progreso de los alumnos en el panel del profesor.

DECISIÓN DE ARQUITECTURA: se eligió la opción (b) — endpoint HTTP nativo
de Maubot (webapp: true en maubot.yaml).  No se requiere ningún
microservicio separado: el propio plugin expone el endpoint mediante el
decorador @web.get("/progreso") de maubot.handlers.web.

URL del endpoint (patrón Maubot):
  http://<maubot-host>/_matrix/maubot/plugin/<instance_id>/progreso

La URL exacta de la instancia desplegada se lee de la configuración global
del plugin (block_gitmetrics/bot_progress_url), que el administrador rellena
con el valor de self.webapp_url que el bot imprime en su log de arranque.

Autenticación: Bearer token compartido (progress_api_token en base-config.yaml
del bot = bot_progress_token en los ajustes de Moodle).

Esta clase cachea los resultados en block_gitmetrics_progress_cache igual
que metrics_cache.php cachea las métricas de GitHub/GitLab.
--8<-- [end:class_desc]
*/

/**
 * Cliente HTTP para el endpoint de progreso del bot Maubot.
 *
 * Consume GET <bot_progress_url>/progreso?curso_id=<n>
 * con cabecera Authorization: Bearer <bot_progress_token>
 * y devuelve un array de filas con:
 *   id_pseudo, curso_id, num_sesiones, ultima_sesion,
 *   ultimo_resumen, conceptos_dominados
 */
class student_progress {

    const CACHE_TABLE = 'block_gitmetrics_progress_cache';

    private \moodle_database $db;

    public function __construct(?\moodle_database $db = null) {
        global $DB;
        $this->db = $db ?: $DB;
    }

    // --8<-- [start:get_progress]
    /**
     * Devuelve el progreso de los alumnos de un curso.
     * Usa caché con TTL configurable (mismo TTL que las métricas Git).
     *
     * @param  int    $course_id  ID del curso de Moodle
     * @param  int    $block_id   ID de la instancia del bloque
     * @return array|null  Array de filas de progreso, o null si falla
     */
    public function get_progress(int $course_id, int $block_id): ?array {
        // 1. Intentar desde caché
        $cached = $this->get_from_cache($course_id, $block_id);
        if ($cached !== null) {
            return $cached;
        }

        // 2. Llamar al endpoint del bot
        $data = $this->fetch_from_bot($course_id);
        if ($data === null) {
            return null;
        }

        // 3. Guardar en caché
        $this->save_to_cache($course_id, $block_id, $data);
        return $data;
    }
    // --8<-- [end:get_progress]

    // --8<-- [start:fetch_from_bot]
    /**
     * Consulta el endpoint HTTP del bot y devuelve el array de progreso.
     * El token se lee de la configuración global del plugin.
     *
     * @param int $course_id
     * @return array|null
     */
    private function fetch_from_bot(int $course_id): ?array {
        $base_url = rtrim(get_config('block_gitmetrics', 'bot_progress_url') ?: '', '/');
        $token    = get_config('block_gitmetrics', 'bot_progress_token') ?: '';

        if (empty($base_url) || empty($token)) {
            return null; // No configurado: el bloque mostrará un aviso
        }

        $url = $base_url . '/progreso?curso_id=' . urlencode($course_id);

        $curl = new \curl();
        $curl->setHeader(['Authorization: Bearer ' . $token, 'Accept: application/json']);
        $response = $curl->get($url);

        if ($curl->get_errno() !== 0 || $curl->get_info()['http_code'] !== 200) {
            return null;
        }

        $decoded = json_decode($response, true);
        if (json_last_error() !== JSON_ERROR_NONE || !is_array($decoded)) {
            return null;
        }

        return $decoded;
    }
    // --8<-- [end:fetch_from_bot]

    // --8<-- [start:cache]
    private function get_from_cache(int $course_id, int $block_id): ?array {
        $ttl      = $this->get_ttl();
        $min_time = time() - $ttl;

        $record = $this->db->get_record(self::CACHE_TABLE, [
            'blockinstanceid' => $block_id,
            'course_id'       => $course_id,
        ]);

        if (!$record || $record->timemodified < $min_time) {
            return null;
        }

        $data = json_decode($record->progress_json, true);
        return (json_last_error() === JSON_ERROR_NONE) ? $data : null;
    }

    private function save_to_cache(int $course_id, int $block_id, array $data): void {
        $json = json_encode($data, JSON_UNESCAPED_UNICODE);
        $now  = time();

        $existing = $this->db->get_record(self::CACHE_TABLE, [
            'blockinstanceid' => $block_id,
            'course_id'       => $course_id,
        ]);

        if ($existing) {
            $existing->progress_json  = $json;
            $existing->timemodified   = $now;
            $this->db->update_record(self::CACHE_TABLE, $existing);
        } else {
            $record                   = new \stdClass();
            $record->blockinstanceid  = $block_id;
            $record->course_id        = $course_id;
            $record->progress_json    = $json;
            $record->timecreated      = $now;
            $record->timemodified     = $now;
            $this->db->insert_record(self::CACHE_TABLE, $record);
        }
    }

    public function invalidate(int $block_id): void {
        $this->db->delete_records(self::CACHE_TABLE, ['blockinstanceid' => $block_id]);
    }
    // --8<-- [end:cache]

    private function get_ttl(): int {
        $ttl = (int)get_config('block_gitmetrics', 'cache_ttl');
        return $ttl > 0 ? $ttl : 3600;
    }
}
