<?php
namespace block_gitmetrics;

defined('MOODLE_INTERNAL') || die();

/*
--8<-- [start:class_desc]
Interfaz comun para clientes de proveedores Git (GitHub, GitLab...).

Cualquier proveedor debe implementar estos dos metodos para ser
compatible con metrics_calculator.
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
}
