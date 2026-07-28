<?php
define('CLI_SCRIPT', true);
require('/bitnami/moodle/config.php');
$token = get_config('communication_matrix', 'matrixaccesstoken');
$synapse = 'http://matrix-synapse:8008';
$roomid = '!wNhRfYcZDKAMMWWsQT:localhost';

$ch = curl_init("{$synapse}/_matrix/client/v3/rooms/".urlencode($roomid)."/invite");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "Authorization: Bearer {$token}",
    "Content-Type: application/json"
]);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(['user_id' => '@student1:localhost']));
$res = curl_exec($ch);
curl_close($ch);
echo "Invite result: " . $res . "\n";
