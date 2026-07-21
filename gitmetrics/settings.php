<?php
// ── AJUSTES GLOBALES DEL PLUGIN block_gitmetrics ──────────────────────────
// El administrador del sitio puede configurar:
//   - Proveedor Git por defecto (GitHub / GitLab)
//   - Tokens de autenticacion para cada proveedor
//   - URL del servidor GitLab
//   - TTL de la cache de metricas
defined('MOODLE_INTERNAL') || die();

if ($ADMIN->fulltree) {

    // ── Proveedor Git por defecto ─────────────────────────────────────────
    $settings->add(new admin_setting_configselect(
        'block_gitmetrics/default_provider',
        get_string('default_provider', 'block_gitmetrics'),
        get_string('default_provider_desc', 'block_gitmetrics'),
        'github',
        [
            'github' => get_string('provider_github', 'block_gitmetrics'),
            'gitlab' => get_string('provider_gitlab', 'block_gitmetrics'),
        ]
    ));

    // ── Seccion GitHub ────────────────────────────────────────────────────
    $settings->add(new admin_setting_heading(
        'block_gitmetrics/heading_github',
        get_string('heading_github', 'block_gitmetrics'),
        ''
    ));

    // Token GitHub (sin token: 60 req/hora; con token: 5000/hora)
    $settings->add(new admin_setting_configpasswordunmask(
        'block_gitmetrics/github_token',
        get_string('github_token', 'block_gitmetrics'),
        get_string('github_token_desc', 'block_gitmetrics'),
        ''
    ));

    // ── Seccion GitLab ────────────────────────────────────────────────────
    $settings->add(new admin_setting_heading(
        'block_gitmetrics/heading_gitlab',
        get_string('heading_gitlab', 'block_gitmetrics'),
        ''
    ));

    // URL base del servidor GitLab (OSL, local o gitlab.com)
    $settings->add(new admin_setting_configtext(
        'block_gitmetrics/gitlab_url',
        get_string('gitlab_url', 'block_gitmetrics'),
        get_string('gitlab_url_desc', 'block_gitmetrics'),
        'https://gitlab.com',
        PARAM_URL
    ));

    // Token GitLab (PRIVATE-TOKEN)
    $settings->add(new admin_setting_configpasswordunmask(
        'block_gitmetrics/gitlab_token',
        get_string('gitlab_token', 'block_gitmetrics'),
        get_string('gitlab_token_desc', 'block_gitmetrics'),
        ''
    ));

    // ── Configuracion general ─────────────────────────────────────────────
    $settings->add(new admin_setting_heading(
        'block_gitmetrics/heading_general',
        get_string('heading_general', 'block_gitmetrics'),
        ''
    ));

    // TTL de la cache
    $settings->add(new admin_setting_configtext(
        'block_gitmetrics/cache_ttl',
        get_string('cache_ttl', 'block_gitmetrics'),
        get_string('cache_ttl_desc', 'block_gitmetrics'),
        '3600',
        PARAM_INT
    ));

    // Rama por defecto del repositorio
    $settings->add(new admin_setting_configtext(
        'block_gitmetrics/default_branch',
        get_string('default_branch', 'block_gitmetrics'),
        get_string('default_branch_desc', 'block_gitmetrics'),
        'main',
        PARAM_ALPHANUMEXT
    ));

    // ── Sección Obsidian (opcional, eliminar para desactivar) ─────────────────
    // OBSIDIAN_OPTIONAL_START
    // Para desactivar: elimina desde OBSIDIAN_OPTIONAL_START hasta OBSIDIAN_OPTIONAL_END
    // y borra los archivos: classes/obsidian_exporter.php y cli/export_obsidian.php
    $settings->add(new admin_setting_heading(
        'block_gitmetrics/heading_obsidian',
        get_string('heading_obsidian', 'block_gitmetrics'),
        get_string('heading_obsidian_desc', 'block_gitmetrics')
    ));

    // Toggle para habilitar o deshabilitar la integración con Obsidian
    $settings->add(new admin_setting_configcheckbox(
        'block_gitmetrics/obsidian_enabled',
        get_string('obsidian_enabled', 'block_gitmetrics'),
        get_string('obsidian_enabled_desc', 'block_gitmetrics'),
        0  // Desactivado por defecto
    ));

    // Ruta local del vault de Obsidian (carpeta en el sistema de archivos del servidor o del usuario)
    $settings->add(new admin_setting_configtext(
        'block_gitmetrics/obsidian_vault_path',
        get_string('obsidian_vault_path', 'block_gitmetrics'),
        get_string('obsidian_vault_path_desc', 'block_gitmetrics'),
        '',
        PARAM_RAW
    ));

    // Nombre del vault tal y como Obsidian lo registra (nombre de la carpeta del vault)
    $settings->add(new admin_setting_configtext(
        'block_gitmetrics/obsidian_vault_name',
        get_string('obsidian_vault_name', 'block_gitmetrics'),
        get_string('obsidian_vault_name_desc', 'block_gitmetrics'),
        'OKF-Vault',
        PARAM_TEXT
    ));
    // OBSIDIAN_OPTIONAL_END
}
