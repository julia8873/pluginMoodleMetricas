<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

/*
--8<-- [start:class_desc]
Interfaz comun para clientes de proveedores Git (GitHub, GitLab...).

Metodos de solo lectura (implementados por todos los proveedores):
  - get_tree           -> arbol recursivo de nodos del repositorio
  - get_file_content   -> contenido raw de un fichero

Metodos de escritura (aprovisionamiento de repos de alumno):
  - create_repo_from_template -> crea un repo a partir de una plantilla
  - fork_repo                 -> hace fork de un repo existente
  - add_collaborator          -> añade un colaborador con un rol dado

Los proveedores que no soporten un metodo de escritura deben lanzar
\Exception('No implementado para <proveedor>') — jamas dejar el cuerpo vacio.
--8<-- [end:class_desc]
*/
interface git_provider_interface {

    /**
     * Devuelve el arbol recursivo de nodos del repositorio.
     *
     * Cada nodo debe tener al menos:
     *   - 'path'  => ruta relativa dentro del repo
     *   - 'type'  => 'blob' (fichero) o 'tree' (directorio)
     *   - 'size'  => tamaño en bytes (0 si es directorio o desconocido)
     *
     * @param  string $owner  Propietario o grupo/namespace del repo
     * @param  string $repo   Nombre del repositorio
     * @param  string $branch Rama a analizar
     * @return array  Lista de nodos
     * @throws \Exception Si la API devuelve error
     */
    // --8<-- [start:get_tree]
    public function get_tree(string $owner, string $repo, string $branch): array;
    // --8<-- [end:get_tree]

    /**
     * Descarga el contenido raw (texto plano) de un fichero del repositorio.
     *
     * @param  string $owner
     * @param  string $repo
     * @param  string $path   Ruta relativa dentro del repo
     * @param  string $branch
     * @return string Contenido del fichero (puede estar vacio si es inaccesible)
     */
    // --8<-- [start:get_file_content]
    public function get_file_content(string $owner, string $repo, string $path, string $branch): string;
    // --8<-- [end:get_file_content]

    // -------------------------------------------------------------------------
    // Operaciones de escritura (aprovisionamiento de repos de alumno)
    // -------------------------------------------------------------------------

    /**
     * Crea un nuevo repositorio en $new_namespace a partir de una plantilla.
     *
     * En GitHub se usa el endpoint POST /repos/{template_owner}/{template_repo}/generate.
     * En GitLab no existe un equivalente directo; el implementador debe lanzar
     * una excepcion explicita si el proveedor no lo soporta.
     *
     * @param  string $template_owner  Propietario del repo plantilla
     * @param  string $template_repo   Nombre del repo plantilla
     * @param  string $new_namespace   Cuenta u organizacion donde crear el repo nuevo
     * @param  string $new_name        Nombre del repo nuevo
     * @return string URL HTML del repo creado
     * @throws \Exception Si la API devuelve error o el proveedor no lo soporta
     */
    // --8<-- [start:create_repo_from_template]
    public function create_repo_from_template(
        string $template_owner,
        string $template_repo,
        string $new_namespace,
        string $new_name
    ): string;
    // --8<-- [end:create_repo_from_template]

    /**
     * Hace fork de un repositorio existente en $target_namespace con un nombre dado.
     *
     * Alternativa a create_repo_from_template cuando el repo origen NO esta marcado
     * como plantilla en GitHub, o para proveedores que soporten fork pero no la API de templates.
     *
     * @param  string $source_owner     Propietario del repo origen
     * @param  string $source_repo      Nombre del repo origen
     * @param  string $target_namespace Cuenta u organizacion donde crear el fork
     * @param  string $new_name         Nombre del fork
     * @return string URL HTML del fork creado
     * @throws \Exception Si la API devuelve error o el proveedor no lo soporta
     */
    // --8<-- [start:fork_repo]
    public function fork_repo(
        string $source_owner,
        string $source_repo,
        string $target_namespace,
        string $new_name
    ): string;
    // --8<-- [end:fork_repo]

    /**
     * Añade un colaborador a un repositorio con el rol indicado.
     *
     * En GitHub el rol se mapea a un 'permission' (pull/push/maintain/admin).
     * En GitLab se mapea a un access_level numerico (10/20/30/40/50).
     *
     * @param  string $owner    Propietario del repo
     * @param  string $repo     Nombre del repo
     * @param  string $username Login del usuario a añadir
     * @param  string $role     Rol semantico: 'guest'|'reporter'|'developer'|'maintainer'|'owner'
     * @return bool   true si el colaborador fue añadido o ya existia
     * @throws \Exception Si la API devuelve un error no recuperable
     */
    // --8<-- [start:add_collaborator]
    public function add_collaborator(
        string $owner,
        string $repo,
        string $username,
        string $role = 'maintainer'
    ): bool;
    // --8<-- [end:add_collaborator]
}
