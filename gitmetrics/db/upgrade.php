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

    // 2026072800 — Tablas de aprovisionamiento de repos de alumno (Paso 3).
    //   block_gitmetrics_course_repo  → un repo de curso por course_id (status: pendiente|creado|error)
    //   block_gitmetrics_student_fork → un fork personal por course_id+userid
    if ($oldversion < 2026072800) {

        // -- block_gitmetrics_course_repo ----------------------------------
        $table = new xmldb_table('block_gitmetrics_course_repo');

        $table->add_field('id',          XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL, XMLDB_SEQUENCE);
        $table->add_field('course_id',   XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);
        $table->add_field('repo_url',    XMLDB_TYPE_CHAR,   '500', null, XMLDB_NOTNULL);
        $table->add_field('provider',    XMLDB_TYPE_CHAR,    '20', null, XMLDB_NOTNULL);
        $table->add_field('status',      XMLDB_TYPE_CHAR,    '20', null, XMLDB_NOTNULL, null, 'pendiente');
        $table->add_field('error_msg',   XMLDB_TYPE_TEXT,    null, null, null);          // nullable
        $table->add_field('timecreated', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);

        $table->add_key('primary', XMLDB_KEY_PRIMARY, ['id']);
        $table->add_index('course', XMLDB_INDEX_UNIQUE, ['course_id']);

        if (!$dbman->table_exists($table)) {
            $dbman->create_table($table);
        }

        // -- block_gitmetrics_student_fork ---------------------------------
        $table2 = new xmldb_table('block_gitmetrics_student_fork');

        $table2->add_field('id',          XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL, XMLDB_SEQUENCE);
        $table2->add_field('course_id',   XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);
        $table2->add_field('userid',      XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);
        $table2->add_field('id_pseudo',   XMLDB_TYPE_CHAR,    '36', null, XMLDB_NOTNULL);
        $table2->add_field('fork_url',    XMLDB_TYPE_CHAR,   '500', null, null);          // nullable
        $table2->add_field('status',      XMLDB_TYPE_CHAR,    '20', null, XMLDB_NOTNULL, null, 'pendiente');
        $table2->add_field('error_msg',   XMLDB_TYPE_TEXT,    null, null, null);          // nullable
        $table2->add_field('timecreated', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);

        $table2->add_key('primary', XMLDB_KEY_PRIMARY, ['id']);
        $table2->add_index('course_user', XMLDB_INDEX_UNIQUE, ['course_id', 'userid']);

        if (!$dbman->table_exists($table2)) {
            $dbman->create_table($table2);
        }

        upgrade_block_savepoint(true, 2026072800, 'gitmetrics');
    }

    if ($oldversion < 2026072805) {
        $table = new xmldb_table('block_gitmetrics_course_repo');
        $field = new xmldb_field('attempts', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL, null, '0', 'error_msg');
        if (!$dbman->field_exists($table, $field)) {
            $dbman->add_field($table, $field);
        }

        $table2 = new xmldb_table('block_gitmetrics_student_fork');
        $field2 = new xmldb_field('attempts', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL, null, '0', 'error_msg');
        if (!$dbman->field_exists($table2, $field2)) {
            $dbman->add_field($table2, $field2);
        }

        upgrade_block_savepoint(true, 2026072805, 'gitmetrics');
    }

    return true;
}