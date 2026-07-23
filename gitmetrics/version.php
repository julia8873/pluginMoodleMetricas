<?php
// Comprobación: si MOODLE_INTERNAL no está definida, terminar.
defined('MOODLE_INTERNAL') || die();

$plugin->component = 'block_gitmetrics';
$plugin->version   = 2026072100;
$plugin->requires  = 2022041900;  // Moodle 4.0+
$plugin->maturity  = MATURITY_STABLE;