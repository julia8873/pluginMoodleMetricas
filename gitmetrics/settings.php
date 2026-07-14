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
}
