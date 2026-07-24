<?php
/*
--8<-- [start:file_desc]
Definición de versión e información básica del plugin Gitmetrics.
--8<-- [end:file_desc]
*/
// Comprobación: si MOODLE_INTERNAL no está definida, terminar.
defined('MOODLE_INTERNAL') || die();

// --8<-- [start:version_definition]
$plugin->component = 'block_gitmetrics';
$plugin->version   = 2026072100;
$plugin->requires  = 2022041900;  // Moodle 4.0+
$plugin->maturity  = MATURITY_STABLE;
// --8<-- [end:version_definition]