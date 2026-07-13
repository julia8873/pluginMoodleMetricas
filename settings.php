<?php
// ── AJUSTES GLOBALES DEL PLUGIN block_gitmetrics ──────────────────────────
// El administrador del sitio puede configurar:
//   - Token de GitHub (para mayor rate-limit y repos privados)
//   - TTL de la caché de métricas
defined('MOODLE_INTERNAL') || die();

if ($ADMIN->fulltree) {

    // ── Token de la API de GitHub ─────────────────────────────────────────
    // Sin token: 60 peticiones/hora por IP.
    // Con token (Personal Access Token o Fine-Grained Token): 5 000/hora.
    $settings->add(new admin_setting_configpasswordunmask(
        'block_gitmetrics/github_token',
        get_string('github_token', 'block_gitmetrics'),
        get_string('github_token_desc', 'block_gitmetrics'),
        ''
    ));

    // ── TTL de la caché ───────────────────────────────────────────────────
    // Tiempo (en segundos) durante el que se reutilizan los resultados
    // almacenados en BD sin volver a llamar a la API de GitHub.
    $settings->add(new admin_setting_configtext(
        'block_gitmetrics/cache_ttl',
        get_string('cache_ttl', 'block_gitmetrics'),
        get_string('cache_ttl_desc', 'block_gitmetrics'),
        '3600',
        PARAM_INT
    ));

    // ── Rama por defecto del repositorio ─────────────────────────────────
    $settings->add(new admin_setting_configtext(
        'block_gitmetrics/default_branch',
        get_string('default_branch', 'block_gitmetrics'),
        get_string('default_branch_desc', 'block_gitmetrics'),
        'main',
        PARAM_ALPHANUMEXT
    ));
}