<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Formulario de configuracion por instancia del bloque.
 * El profesor elige el proveedor (GitHub o GitLab) y pega la URL
 * del repositorio que desea analizar en su asignatura o curso.
 */
class block_gitmetrics_edit_form extends block_edit_form {

    protected function specific_definition($mform) {

        // -- Seccion principal ----------------------------------------------
        $mform->addElement('header', 'configheader', get_string('blocksettings', 'block'));

        // Proveedor Git
        $mform->addElement(
            'select',
            'config_provider',
            get_string('provider', 'block_gitmetrics'),
            [
                'github' => get_string('provider_github', 'block_gitmetrics'),
                'gitlab' => get_string('provider_gitlab', 'block_gitmetrics'),
            ]
        );
        $mform->setType('config_provider', PARAM_ALPHA);
        $default_provider = get_config('block_gitmetrics', 'default_provider') ?: 'github';
        $mform->setDefault('config_provider', $default_provider);
        $mform->addHelpButton('config_provider', 'provider', 'block_gitmetrics');

        // URL del repositorio (GitHub o GitLab)
        $mform->addElement(
            'text',
            'config_repo_url',
            get_string('repo_url', 'block_gitmetrics'),
            ['size' => 65, 'placeholder' => 'https://github.com/usuario/repositorio  o  https://gitlab.osl.ugr.es/grupo/repositorio']
        );
        $mform->setType('config_repo_url', PARAM_URL);
        $mform->addHelpButton('config_repo_url', 'repo_url', 'block_gitmetrics');

        // Rama del repositorio (opcional, por defecto 'main')
        $mform->addElement(
            'text',
            'config_branch',
            get_string('branch', 'block_gitmetrics'),
            ['size' => 20, 'placeholder' => 'main']
        );
        $mform->setType('config_branch', PARAM_ALPHANUMEXT);
        $mform->setDefault('config_branch', 'main');

        // Forzar refresco de cache
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