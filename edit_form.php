<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Formulario de configuración por instancia del bloque.
 * El profesor puede introducir la URL del repositorio GitHub
 * que desea analizar, específicamente para su asignatura/curso.
 */
class block_gitmetrics_edit_form extends block_edit_form {

    protected function specific_definition($mform) {

        // ── Sección principal ──────────────────────────────────────────────
        $mform->addElement('header', 'configheader', get_string('blocksettings', 'block'));

        // URL del repositorio GitHub
        $mform->addElement(
            'text',
            'config_github_url',
            get_string('github_url', 'block_gitmetrics'),
            ['size' => 60, 'placeholder' => 'https://github.com/usuario/repositorio']
        );
        $mform->setType('config_github_url', PARAM_URL);
        $mform->addHelpButton('config_github_url', 'github_url', 'block_gitmetrics');

        // Rama del repositorio (opcional, por defecto 'main')
        $mform->addElement(
            'text',
            'config_branch',
            get_string('branch', 'block_gitmetrics'),
            ['size' => 20, 'placeholder' => 'main']
        );
        $mform->setType('config_branch', PARAM_ALPHANUMEXT);
        $mform->setDefault('config_branch', 'main');

        // Forzar refresco de caché
        $mform->addElement(
            'advcheckbox',
            'config_force_refresh',
            get_string('force_refresh', 'block_gitmetrics'),
            get_string('force_refresh_desc', 'block_gitmetrics')
        );
        $mform->setType('config_force_refresh', PARAM_BOOL);
        $mform->setDefault('config_force_refresh', 0);
    }
}