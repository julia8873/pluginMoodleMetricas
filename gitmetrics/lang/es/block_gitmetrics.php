<?php
// ── Cadenas de idioma (Español) para block_gitmetrics ────────────────────

// Plugin
$string['pluginname']                  = 'Métricas de Base de Conocimiento Git';
$string['gitmetrics:addinstance']      = 'Añadir un bloque de Métricas Git';
$string['gitmetrics:myaddinstance']    = 'Añadir un bloque de Métricas Git a Mi Moodle';
$string['gitmetrics:viewmetrics']      = 'Ver Métricas Git';

// Ajustes globales
$string['github_token']                = 'Token de API de GitHub';
$string['github_token_desc']           = 'Token de Acceso Personal opcional (clásico o de grano fino). Sin token, la API de GitHub permite 60 peticiones/hora por IP. Con token, el límite sube a 5.000/hora. Requerido para repositorios privados.';
$string['cache_ttl']                   = 'TTL de la caché (segundos)';
$string['cache_ttl_desc']              = 'Tiempo (en segundos) durante el que se reutilizan las métricas calculadas antes de volver a consultar la API. Por defecto: 3600 (1 hora).';
$string['default_branch']             = 'Rama por defecto';
$string['default_branch_desc']        = 'Rama de Git que se analizará si no se especifica ninguna en la instancia del bloque (p. ej. main o master).';

// Formulario de instancia
$string['github_url']                  = 'URL del Repositorio GitHub';
$string['github_url_help']             = 'Pega la URL pública completa del repositorio GitHub a analizar, p. ej. https://github.com/usuario/repositorio';
$string['branch']                      = 'Rama';
$string['force_refresh']               = 'Forzar refresco de caché';
$string['force_refresh_desc']          = 'Marca esta casilla para descartar los resultados en caché y recalcular todas las métricas en la próxima carga.';

// Encabezados de sección
$string['section_volume']              = 'Volumen y Estructura';
$string['section_network']             = 'Red y Conectividad';
$string['section_tags']                = 'Métricas de Etiquetas';
$string['section_format']              = 'Validación de Formato';

// Etiquetas de métricas de volumen
$string['metric_md_files']             = 'Archivos Markdown';
$string['metric_total_files']          = 'Total de archivos';
$string['metric_dirs']                 = 'Directorios';
$string['metric_total_size']           = 'Tamaño total';
$string['metric_avg_size']             = 'Tamaño medio por archivo';
$string['metric_avg_words']            = 'Palabras medias por archivo';
$string['metric_max_words']            = 'Máx. palabras en un archivo';
$string['metric_max_depth']            = 'Profundidad máxima de directorios';
$string['metric_avg_depth']            = 'Profundidad media';
$string['essential_files']             = 'Archivos esenciales';

// Etiquetas de métricas de red
$string['metric_total_nodes']          = 'Total de nodos';
$string['metric_avg_connections']      = 'Media de nodos conectados';
$string['metric_orphan_count']         = 'Nodos huérfanos';
$string['metric_orphan_rate']          = 'Tasa de nodos huérfanos';
$string['metric_total_links']          = 'Total de enlaces internos';
$string['metric_link_density']         = 'Densidad de enlaces';
$string['link_density_desc']           = 'Enlaces internos / total de palabras';

// Etiquetas de métricas de etiquetas
$string['metric_unique_tags']          = 'Etiquetas únicas';
$string['metric_tag_usage']            = 'Usos totales de etiquetas';
$string['metric_files_with_tags']      = 'Archivos con etiquetas';
$string['metric_files_without_tags']   = 'Archivos sin etiquetas';
$string['metric_hamming_avg']          = 'Distancia Hamming media';
$string['hamming_desc']                = 'Distancia de Hamming media entre pares de vectores binarios de etiquetas (mayor = etiquetado más diverso)';
$string['top_tags']                    = 'Etiquetas más usadas';

// Etiquetas de métricas de formato
$string['metric_frontmatter_rate']     = 'Cobertura de frontmatter';
$string['metric_valid_frontmatter']    = 'Frontmatter válido';
$string['metric_valid_markdown']       = 'Archivos Markdown válidos';
$string['metric_valid_markdown_rate']  = 'Tasa de Markdown válido';
$string['frontmatter_errors']          = 'Errores de frontmatter';

// Estado / varios
$string['no_repo_configured']          = 'No hay ninguna URL de repositorio configurada. Edita este bloque y pega la URL de un repositorio de GitHub.';
$string['last_updated']                = 'Última actualización';
$string['view_repo']                   = 'Ver repositorio';
$string['refresh_metrics']             = 'Actualizar métricas';
$string['files_detail']                = 'Detalle de archivos';
$string['bytes']                       = 'bytes';
$string['words']                       = 'palabras';
$string['present']                     = 'Presente';
$string['missing']                     = 'Ausente';

// Errores
$string['error_invalid_url']           = 'URL de GitHub no válida. Formato esperado: https://github.com/propietario/repositorio';
$string['error_api']                   = 'No se pudo conectar a la API de GitHub. Comprueba que el repositorio es público o que hay un token válido configurado.';
$string['error_json']                  = 'Respuesta inesperada de la API de GitHub (error al parsear JSON).';
$string['error_repo']                  = 'Repositorio no encontrado o inaccesible';
$string['error_branch']                = 'Rama no encontrada. Prueba a cambiar la rama en los ajustes del bloque.';

// Obsidian (opcional) — eliminar este bloque junto con classes/obsidian_exporter.php y cli/export_obsidian.php
$string['heading_obsidian']            = 'Integracion con Obsidian (opcional)';
$string['heading_obsidian_desc']       = 'Permite abrir documentos directamente en Obsidian y exportar la base de conocimiento a un vault local. Esta funcion es completamente opcional; si no la necesitas, puedes ignorarla o desactivarla.';
$string['obsidian_enabled']            = 'Habilitar integración con Obsidian';
$string['obsidian_enabled_desc']       = 'Cuando esta activado, aparecera un boton "Obsidian" junto a cada documento que abre la nota directamente en la aplicacion Obsidian instalada en el ordenador del usuario.';
$string['obsidian_vault_path']         = 'Ruta local del vault de Obsidian';
$string['obsidian_vault_path_desc']    = 'Ruta absoluta en el sistema de archivos del usuario donde se encuentra (o se creará) el vault de Obsidian. Ejemplo: /home/julia/Documents/OKF-Vault o C:\\Users\\julia\\Documents\\OKF-Vault';
$string['obsidian_vault_name']         = 'Nombre del vault de Obsidian';
$string['obsidian_vault_name_desc']    = 'Nombre exacto del vault tal y como Obsidian lo registró al crearlo (nombre de la carpeta del vault). Este nombre se usa para construir los enlaces obsidian://.';
$string['task_sync_obsidian']          = 'Sincronizacion programada del vault de Obsidian';
