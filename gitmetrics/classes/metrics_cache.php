<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

/**
 * Gestión de la caché de métricas en la base de datos de Moodle.
 *
 * Almacena los resultados del análisis en la tabla block_gitmetrics_cache
 * indexados por (blockinstanceid + MD5 de la URL del repositorio).
 *
 * El TTL (time-to-live) se lee de la configuración global del plugin.
 */
class metrics_cache {

    const TABLE = 'block_gitmetrics_cache';

    private \moodle_database $db;

    public function __construct(?\moodle_database $db = null) {
        global $DB;
        $this->db = $db ?: $DB;
    }

    // -------------------------------------------------------------------------
    // API pública
    // ─────────────────────────────────────────────────────────────────────

    /**
     * Recupera métricas cacheadas si existen y no han caducado.
     *
     * @param  string $repo_url  URL del repositorio
     * @param  int    $block_id  ID de la instancia del bloque
     * @return array|null  Array de métricas, o null si no hay caché válida
     */
    public function get(string $repo_url, int $block_id): ?array {
        $ttl      = $this->get_ttl();
        $min_time = time() - $ttl;
        $hash     = md5($repo_url);

        $record = $this->db->get_record(self::TABLE, [
            'blockinstanceid' => $block_id,
            'repo_url_hash'   => $hash,
        ]);

        if (!$record) {
            return null; // Sin entrada en caché
        }

        if ($record->timemodified < $min_time) {
            return null; // Caché caducada
        }

        $data = json_decode($record->metrics_json, true);

        if (json_last_error() !== JSON_ERROR_NONE) {
            // JSON corrupto: eliminar el registro
            $this->db->delete_records(self::TABLE, ['id' => $record->id]);
            return null;
        }

        return $data;
    }

    /**
     * Guarda (o actualiza) las métricas en la caché.
     *
     * @param  string $repo_url  URL del repositorio
     * @param  int    $block_id  ID de la instancia del bloque
     * @param  array  $metrics   Array de métricas a serializar
     */
    public function set(string $repo_url, int $block_id, array $metrics): void {
        $hash    = md5($repo_url);
        $json    = json_encode($metrics, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        $now     = time();

        $existing = $this->db->get_record(self::TABLE, [
            'blockinstanceid' => $block_id,
            'repo_url_hash'   => $hash,
        ]);

        if ($existing) {
            $existing->repo_url      = substr($repo_url, 0, 500); // respetar longitud BD
            $existing->metrics_json  = $json;
            $existing->timemodified  = $now;
            $this->db->update_record(self::TABLE, $existing);
        } else {
            $record                   = new \stdClass();
            $record->blockinstanceid  = $block_id;
            $record->repo_url         = substr($repo_url, 0, 500);
            $record->repo_url_hash    = $hash;
            $record->metrics_json     = $json;
            $record->timecreated      = $now;
            $record->timemodified     = $now;
            $this->db->insert_record(self::TABLE, $record);
        }
    }

    /**
     * Elimina todos los registros de caché de una instancia de bloque.
     * Se usa cuando el usuario fuerza el refresco.
     *
     * @param int $block_id ID de la instancia del bloque
     */
    public function invalidate(int $block_id): void {
        $this->db->delete_records(self::TABLE, ['blockinstanceid' => $block_id]);
    }

    /**
     * Elimina registros de caché cuyo timemodified sea anterior al TTL actual.
     * Útil para un cleanup periódico (p. ej. desde un cron task).
     */
    public function purge_expired(): int {
        $min_time = time() - $this->get_ttl();
        return $this->db->delete_records_select(
            self::TABLE,
            'timemodified < :mintime',
            ['mintime' => $min_time]
        );
    }

    // ─────────────────────────────────────────────────────────────────────
    // Utilidades privadas
    // ─────────────────────────────────────────────────────────────────────

    private function get_ttl(): int {
        $ttl = (int)get_config('block_gitmetrics', 'cache_ttl');
        return $ttl > 0 ? $ttl : 3600;
    }
}
