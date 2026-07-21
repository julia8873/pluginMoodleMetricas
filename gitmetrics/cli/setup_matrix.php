<?php
// -----------------------------------------------------------------------------
// Script CLI para automatizar la configuracion e inicializacion de Matrix
// -----------------------------------------------------------------------------

define('CLI_SCRIPT', true);

require_once(__DIR__ . '/../../../config.php');
require_once($CFG->dirroot . '/course/lib.php');

echo "=== 1. Activando el subsistema de comunicacion de Moodle ===\n";
set_config('enablecommunicationsubsystem', 1);
echo "Subsistema de comunicacion habilitado (enablecommunicationsubsystem = 1).\n";

echo "=== 2. Desbloqueando red interna y puertos para Synapse en cURL ===\n";
set_config('curlsecurityallowedport', "443\n80\n8008\n8081\n8080");
set_config('curlsecurityblockedhosts', '');
// Purgar cache de versiones del servidor por si habia consultas fallidas anteriores
\cache::make('communication_matrix', 'serverversions')->purge();
echo "Puertos 8008, 8081, 8080 permitidos y bloqueo de red local eliminado.\n";

echo "=== 3. Conectando a Synapse para obtener el Access Token automatico ===\n";
$synapseurl = 'http://matrix-synapse:8008';
$ch = curl_init("{$synapseurl}/_matrix/client/v3/login");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    'type' => 'm.login.password',
    'user' => 'admin',
    'password' => 'adminpass123'
]));
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
$res = curl_exec($ch);
curl_close($ch);

$token = '';
if ($res) {
    $data = json_decode($res, true);
    if (!empty($data['access_token'])) {
        $token = $data['access_token'];
        echo "Token obtenido con exito para la cuenta {$data['user_id']}.\n";
    }
}

if (!$token) {
    echo "Aviso: No se pudo obtener el token via API (¿Synapse aun iniciando?). Se mantiene el token existente.\n";
    $token = get_config('communication_matrix', 'matrixaccesstoken') ?: '';
}

echo "=== 4. Configurando el proveedor Matrix en Moodle ===\n";
set_config('matrixhomeserverurl', 'http://matrix-synapse:8008', 'communication_matrix');
set_config('matrixaccesstoken', $token, 'communication_matrix');
set_config('matrixelementurl', 'http://localhost:8081', 'communication_matrix');
echo "Parametros de Matrix guardados correctamente en la base de datos de Moodle.\n";

echo "=== 5. Vinculando sala de Matrix e incluyendo al bot en todos los cursos de Moodle ===\n";
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/matrix_helper.php');
$count = \block_gitmetrics\matrix_helper::process_all_existing_courses();
echo "Se ha comprobado y asegurado la sala de chat y la inclusión del bot (@githubbot:localhost) en {$count} asignaturas.\n";

echo "\n=== CONFIGURACION AUTOMATICA DE MATRIX COMPLETADA ===\n";
