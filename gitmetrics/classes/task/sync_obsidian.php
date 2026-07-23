<?php
// -----------------------------------------------------------------------------
// classes/task/sync_obsidian.php (Módulo Obsidian)
//
// Tarea programada de Moodle (Scheduled Task) para sincronizar automáticamente
// el repositorio Git con el vault local de Obsidian cada hora mediante el
// sistema cron de Moodle.
//
// FLUJO:
//  1. Comprobar si la integración está activada (si no, se cancela).
//  2. Leer la ruta del Vault de Obsidian en el disco duro (ej: /obsidian-vault).
//  3. Cargar el cliente de Git leyendo el token, la URL y la rama de los ajustes.

// en el fichero obsidian_exporter.php:
//  4. Obtener el "Árbol" (Tree) de archivos remotos conectados a la API.
//      eg árbol de asignatura de ecuacionesII:
/*
    [
        {
            "path": "ecuacionesII",
            "type": "tree",
            "mode": "040000",
            "id": "e45a23f99b1a5e",
            "name": "ecuacionesII"
        },
        {
            "path": "ecuacionesII/introduccion.md",
            "type": "blob",
            "mode": "100644",
            "id": "3b18e510fa43a41c1c",
            "name": "introduccion.md"
        },
    ]
*/
//  5. Comprobar si se ha cambiado un fichero comparando el SHA (el id) de los archivos.
//  6. Descargar el contenido de los archivos que sean nuevos o hayan cambiado.
//  7. "Mandar" los datos a Obsidian: Moodle guarda el archivo físicamente en la 
//    carpeta del disco duro (usando file_put_contents). Obsidian detecta el 
//    archivo instantáneamente.
//  8. [Por implementar] Revisar archivos borrados: Se comparan los archivos de la carpeta local con
//    los de Git y se borran los que sobren (nodos fantasma).
// -----------------------------------------------------------------------------

namespace block_gitmetrics\task;

// Verificamos que este script se está ejecutando dentro del entorno de Moodle (por seguridad).
defined('MOODLE_INTERNAL') || die();

// Importamos la clase principal encargada de la exportación a Obsidian
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/obsidian_exporter.php');

// Definimos la clase de la tarea, que hereda de \core\task\scheduled_task para ser reconocida por el cron de Moodle.
class sync_obsidian extends \core\task\scheduled_task {

    /**
     * Devuelve el nombre de la tarea programada.
     * Al entrar en Administración del sitio > Servidor > Tareas programadas, 
     * Moodle llama internamente a esta función para saber qué nombre mostrar en la tabla.
     * Saldrá como "Sincronización programada del vault de Obsidian"
     */
    public function get_name(): string {
        // Llama a la función de Moodle get_string para obtener el nombre traducido desde el fichero de idioma.
        return get_string('task_sync_obsidian', 'block_gitmetrics');
    }

    /**
     * Ejecuta la sincronización automática con el vault.
     */
    public function execute(): void {
        // Traemos la variable global $CFG que contiene la configuración general de Moodle (rutas, etc).
        global $CFG;

        // [PASO 1 DEL FLUJO] Comprobar si la integración está activada
        // Leemos la configuración del bloque para saber si la integración con Obsidian está activada (devuelve true o false).
        $obsidian_enabled = (bool) get_config('block_gitmetrics', 'obsidian_enabled');
        
        // Si no está activada:
        if (!$obsidian_enabled) {
            // escribir en log del cron
            mtrace('Sincronizacion Obsidian: desactivada en los ajustes del bloque.');
            return;
        }

        // [PASO 2 DEL FLUJO] Leer la ruta del Vault de Obsidian en el disco duro
        // Leemos la configuración del bloque para obtener la ruta del disco duro donde está el vault de Obsidian.
        // Moodle lee de su memoria RAM en vez de la BD 
        $vault_path = get_config('block_gitmetrics', 'obsidian_vault_path');
        
        if (empty($vault_path)) {
            // escribir en log del cron
            mtrace('Sincronizacion Obsidian: ruta del vault no configurada.');
            return;
        }

        // Cargamos la librería de ficheros de Moodle, útil para operaciones HTTP internas y gestión del sistema.
        require_once($CFG->libdir . '/filelib.php');
        
        // Importamos la interfaz común que deben cumplir todos los proveedores Git.
        require_once($CFG->dirroot . '/blocks/gitmetrics/classes/git_provider_interface.php');
        
        // Importamos el cliente específico para conectarse a repositorios de GitHub.
        require_once($CFG->dirroot . '/blocks/gitmetrics/classes/github_client.php');
        
        // Importamos el cliente específico para conectarse a repositorios de GitLab.
        require_once($CFG->dirroot . '/blocks/gitmetrics/classes/gitlab_client.php');

        // [PASO 3 DEL FLUJO] Cargar el cliente de Git leyendo el token, la URL y la rama
        // Leemos la configuración para saber qué proveedor Git se está usando. Si está vacío, asumimos 'gitlab'.
        $provider = get_config('block_gitmetrics', 'default_provider') ?: 'gitlab';
        
        // Leemos la URL del repositorio remoto.
        $repourl  = get_config('block_gitmetrics', 'repo_url') ?: 'https://gitlab.com/julia8873/BdC';
        
        // Leemos la rama a sincronizar (ej. main o master). Si está vacía, usamos 'main'.
        $branch   = get_config('block_gitmetrics', 'default_branch') ?: 'main';

        if ($provider === 'github') {
            // Obtenemos el token de seguridad de GitHub desde los ajustes.
            $token  = get_config('block_gitmetrics', 'github_token') ?: '';
            // Creamos una nueva instancia del cliente de GitHub inyectándole el token.
            $client = new \block_gitmetrics\github_client($token);
        } else { // Gitlab
            // Obtenemos el token de seguridad privado de GitLab desde los ajustes.
            $token      = get_config('block_gitmetrics', 'gitlab_token') ?: '';
            // Obtenemos la URL base del servidor GitLab (ej. https://gitlab.osl.ugr.es) desde los ajustes.
            $gitlab_url = get_config('block_gitmetrics', 'gitlab_url') ?: 'https://gitlab.com';
            // Creamos una nueva instancia del cliente de GitLab pasándole la URL y el token.
            $client     = new \block_gitmetrics\gitlab_client($gitlab_url, $token);
        }

        // Escribimos en el log del cron avisando de que va a comenzar la sincronización y la ruta de destino.
        mtrace("Iniciando sincronizacion programada hacia el vault: {$vault_path}");
        
        // [PASOS 4-8: Llamamos a obsidian_exporter.php]
        // Instanciamos el exportador de Obsidian pasándole el cliente (para que se descargue las cosas), la url del repo, la ruta local y la rama.
        $exporter = new \block_gitmetrics\obsidian_exporter($client, $repourl, $vault_path, $branch);
        
        // Exportamos. Guardamos el array de estadísticas de vuelta en $stats.
        $stats    = $exporter->export();

        // Escribimos en el log del cron el resumen de lo ocurrido 
        // (cuántos archivos se han descargado y cuántos se han ignorado por no tener cambios).
        mtrace("Sincronizacion completada: {$stats['written']} escritos, {$stats['skipped']} sin cambios.");
        
        // Comprobamos si el proceso de exportación devolvió algún error en su array de estadísticas.
        if (!empty($stats['errors'])) {
            mtrace("Errores en sincronizacion programada:");
            foreach ($stats['errors'] as $err) {
                mtrace("  - {$err}");
            }
        }
    }
}
