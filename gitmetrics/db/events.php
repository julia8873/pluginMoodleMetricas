<?php
defined('MOODLE_INTERNAL') || die();

$observers = [
    [
        'eventname'   => '\core\event\course_created',
        'callback'    => '\block_gitmetrics\observer::course_created',
        'internal'    => false,
    ],
    [
        'eventname'   => '\core\event\role_assigned',
        'callback'    => '\block_gitmetrics\observer::teacher_assigned',
        'internal'    => false,
    ],
    [
        'eventname'   => '\core\event\role_assigned',
        'callback'    => '\block_gitmetrics\observer::student_enrolled',
        'internal'    => false,
    ],
];
