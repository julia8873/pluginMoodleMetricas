<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Función de upgrade para block_gitmetrics.
 * Se ejecuta cuando Moodle detecta que la versión del plugin ha cambiado.
 *
 * @param int $oldversion Versión anterior instalada
 * @return bool
 */
function xmldb_block_gitmetrics_upgrade($oldversion) {
    global $DB;
    $dbman = $DB->get_manager();

    // 2026072700 — Tabla de caché de progreso de alumnos (puente bot → Moodle).
    if ($oldversion < 2026072700) {
        $table = new xmldb_table('block_gitmetrics_progress_cache');

        $table->add_field('id',              XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL, XMLDB_SEQUENCE);
        $table->add_field('blockinstanceid', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);
        $table->add_field('course_id',       XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);
        $table->add_field('progress_json',   XMLDB_TYPE_TEXT,    null, null, XMLDB_NOTNULL);
        $table->add_field('timecreated',     XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);
        $table->add_field('timemodified',    XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);

        $table->add_key('primary', XMLDB_KEY_PRIMARY, ['id']);
        $table->add_index('blockinstance_course', XMLDB_INDEX_NOTUNIQUE, ['blockinstanceid', 'course_id']);

        if (!$dbman->table_exists($table)) {
            $dbman->create_table($table);
        }

        upgrade_block_savepoint(true, 2026072700, 'gitmetrics');
    }

    return true;
}