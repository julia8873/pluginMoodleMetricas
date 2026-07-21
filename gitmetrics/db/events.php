<?php
defined('MOODLE_INTERNAL') || die();

$observers = [
    [
        'eventname'   => '\core\event\course_created',
        'callback'    => '\block_gitmetrics\observer::course_created',
        'internal'    => false,
    ],
];