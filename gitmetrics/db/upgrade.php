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
    // Futuras migraciones se añadirán aquí con bloques if ($oldversion < YYYYMMDD00).
    return true;
}