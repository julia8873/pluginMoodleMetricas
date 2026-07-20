<?php
// -----------------------------------------------------------------------------
// Script CLI para crear la asignatura "Panel de Métricas y BdC"
// -----------------------------------------------------------------------------

define('CLI_SCRIPT', true);

require_once(__DIR__ . '/../../../config.php');
require_once($CFG->dirroot . '/course/lib.php');

global $DB;

$shortname = 'METRICAS_BDC';
$course = $DB->get_record('course', ['shortname' => $shortname]);

if (!$course) {
    $data = new stdClass();
    $data->fullname  = 'Panel de Métricas y BdC';
    $data->shortname = $shortname;
    $data->category  = 1;
    $data->summary   = 'Asignatura y panel central dedicado a evaluar Bases de Conocimiento Git.';
    $data->format    = 'topics';
    $data->visible   = 1;
    $data->newsitems = 0;

    $course = create_course($data);
    echo "Asignatura 'Panel de Métricas y BdC' creada con éxito (ID: {$course->id}).\n";
} else {
    echo "Asignatura 'Panel de Métricas y BdC' ya existía (ID: {$course->id}).\n";
}

// Asegurar que exista el bloque en este curso
$context = context_course::instance($course->id);
if (!$DB->record_exists('block_instances', ['blockname' => 'gitmetrics', 'parentcontextid' => $context->id])) {
    $instance = new stdClass();
    $instance->blockname = 'gitmetrics';
    $instance->parentcontextid = $context->id;
    $instance->showinsubcontexts = 0;
    $instance->pagetypepattern = 'course-view-*';
    $instance->subpagepattern = null;
    $instance->defaultregion = 'side-pre';
    $instance->defaultweight = 0;
    $instance->configdata = base64_encode(serialize((object)[
        'repo_url' => 'https://gitlab.com/julia8873/BdC',
        'provider' => 'gitlab',
        'branch' => 'main'
    ]));
    $instance->timecreated = time();
    $instance->timemodified = time();
    $DB->insert_record('block_instances', $instance);
    echo "Bloque gitmetrics añadido y configurado en la asignatura.\n";
}

// Matriculamos al usuario admin (id = 2) como profesor para que aparezca en "Mis cursos"
$CFG->noemailever = true; // Evitar que Moodle intente enviar correos en entorno CLI/dev sin servidor SMTP
$enrolplugin = enrol_get_plugin('manual');
if ($enrolplugin) {
    $instances = enrol_get_instances($course->id, true);
    $manualinstance = null;
    foreach ($instances as $inst) {
        if ($inst->enrol === 'manual') {
            $manualinstance = $inst;
            break;
        }
    }
    if ($manualinstance) {
        if (!$DB->record_exists('user_enrolments', ['enrolid' => $manualinstance->id, 'userid' => 2])) {
            $enrolplugin->enrol_user($manualinstance, 2, 3);
            echo "Usuario admin matriculado en 'Panel de Métricas y BdC'.\n";
        } else {
            echo "Usuario admin ya estaba matriculado en 'Panel de Métricas y BdC'.\n";
        }
    }
}

// Calculamos las métricas y las inyectamos como los 4 temas de la asignatura
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/github_client.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/markdown_parser.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/metrics_calculator.php');
require_once($CFG->dirroot . '/blocks/gitmetrics/renderer.php');

$token      = get_config('block_gitmetrics', 'gitlab_token') ?: (get_config('block_gitmetrics', 'github_token') ?: '');
$provider   = get_config('block_gitmetrics', 'default_provider') ?: 'gitlab';
$gitlab_url = get_config('block_gitmetrics', 'gitlab_url') ?: 'https://gitlab.com';
$repourl    = 'https://gitlab.com/julia8873/BdC';

$calculator = new \block_gitmetrics\metrics_calculator($token, $provider, $gitlab_url);
$metrics    = $calculator->calculate($repourl, 'main');

global $PAGE;
$PAGE->set_context(context_course::instance($course->id));
$renderer = $PAGE->get_renderer('block_gitmetrics');

// Estilos base de las tarjetas
$styles = '<style>
.gm-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; margin-bottom: 12px; }
.gm-card { display: inline-block; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 14px; margin: 4px; min-width: 130px; }
.gm-card-value { font-size: 20px; font-weight: 700; color: #1e3a8a; }
.gm-card-label { font-size: 11px; color: #475569; }
.gm-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.gm-badge-ok { background: #d1fae5; color: #065f46; }
.gm-tag { display: inline-block; background: #ede9fe; color: #5b21b6; border-radius: 99px; padding: 2px 10px; font-weight: 600; margin: 2px; }
</style>';

// ── Sección 0: Explorador de documentos ──────────────────────────────────────
// Agrupa todos los archivos .md por directorio y genera enlaces al visor integrado.
$courseid_for_links = $course->id;
$branch_link        = 'main';

// Obtener árbol de archivos desde la API
require_once($CFG->dirroot . '/blocks/gitmetrics/classes/gitlab_client.php');
$git_client = new \block_gitmetrics\gitlab_client($gitlab_url, $token);
// Extraer owner/repo de la URL del repo
$repo_parts = array_values(array_filter(explode('/', trim(parse_url($repourl, PHP_URL_PATH), '/'))));
$tree = $git_client->get_tree($repo_parts[0], $repo_parts[1], $branch_link);

// Filtrar solo archivos .md y agrupar por directorio
$md_by_dir = [];
foreach ($tree as $node) {
    if ($node['type'] === 'blob' && str_ends_with(strtolower($node['path']), '.md')) {
        $dir = dirname($node['path']);
        $dir = ($dir === '.') ? '/' : $dir;
        $md_by_dir[$dir][] = $node['path'];
    }
}
ksort($md_by_dir);

// Generar HTML del explorador
$doc_html  = '<style>';
$doc_html .= '.gmdb-wrap{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#1e293b;}';
$doc_html .= '.gmdb-header{background:linear-gradient(135deg,#1e3a5f 0%,#1e40af 100%);border-radius:10px;padding:14px 18px;color:#fff;margin-bottom:16px;}';
$doc_html .= '.gmdb-header-title{font-size:16px;font-weight:800;margin-bottom:4px;}';
$doc_html .= '.gmdb-header-sub{font-size:12px;opacity:.8;}';
$doc_html .= '.gmdb-repo-link{color:#93c5fd;text-decoration:none;}';
$doc_html .= '.gmdb-repo-link:hover{text-decoration:underline;}';

/* Buscador y botones de acción */
$doc_html .= '.gmdb-search-bar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:16px;background:#f8fafc;padding:12px 16px;border-radius:8px;border:1px solid #e2e8f0;}';
$doc_html .= '.gmdb-search-input-wrap{display:flex;align-items:center;gap:8px;flex:1;min-width:260px;position:relative;}';
$doc_html .= '.gmdb-search-input{width:100%;padding:8px 30px 8px 34px;border-radius:6px;border:1px solid #cbd5e1;font-size:14px;color:#1e293b;outline:none;transition:border-color .15s;}';
$doc_html .= '.gmdb-search-input:focus{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.1);}';
$doc_html .= '.gmdb-search-icon{position:absolute;left:10px;top:50%;transform:translateY(-50%);font-size:14px;color:#64748b;pointer-events:none;}';
$doc_html .= '.gmdb-search-clear{position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;color:#94a3b8;font-size:16px;cursor:pointer;padding:2px 6px;border-radius:4px;}';
$doc_html .= '.gmdb-search-clear:hover{color:#334155;background:#e2e8f0;}';
$doc_html .= '.gmdb-search-actions{display:flex;gap:6px;}';
$doc_html .= '.gmdb-btn-toggle{background:#fff;border:1px solid #cbd5e1;color:#334155;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;transition:background .15s;}';
$doc_html .= '.gmdb-btn-toggle:hover{background:#f1f5f9;color:#1e293b;}';
$doc_html .= '.gmdb-search-count{font-size:13px;color:#334155;margin-bottom:12px;padding:8px 12px;background:#eff6ff;border-left:4px solid #2563eb;border-radius:4px;display:none;}';

/* Carpetas colapsables con details/summary */
$doc_html .= 'details.gmdb-folder{background:#fff;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:10px;overflow:hidden;transition:border-color .15s;}';
$doc_html .= 'details.gmdb-folder[open]{border-color:#cbd5e1;box-shadow:0 1px 3px rgba(0,0,0,.05);}';
$doc_html .= 'summary.gmdb-folder-header{background:#f1f5f9;padding:10px 14px;font-size:13px;font-weight:700;color:#334155;cursor:pointer;display:flex;align-items:center;justify-content:space-between;list-style:none;user-select:none;border-bottom:1px solid transparent;transition:background .15s;}';
$doc_html .= 'summary.gmdb-folder-header::-webkit-details-marker{display:none;}';
$doc_html .= 'details.gmdb-folder[open] summary.gmdb-folder-header{border-bottom-color:#e2e8f0;background:#e2e8f0;}';
$doc_html .= 'summary.gmdb-folder-header:hover{background:#e2e8f0;}';
$doc_html .= '.gmdb-folder-title{display:flex;align-items:center;gap:6px;}';
$doc_html .= '.gmdb-toggle-arrow{font-size:11px;color:#64748b;transition:transform .2s;}';
$doc_html .= 'details.gmdb-folder[open] .gmdb-toggle-arrow{transform:rotate(180deg);}';
$doc_html .= '.gmdb-folder-body{padding:4px 0;}';
$doc_html .= '.gmdb-file-row{display:flex;align-items:center;justify-content:space-between;padding:6px 14px;border-bottom:1px solid #f1f5f9;}';
$doc_html .= '.gmdb-file-row:last-child{border-bottom:none;}';
$doc_html .= '.gmdb-file-row:hover{background:#f8fafc;}';
$doc_html .= '.gmdb-file-link{display:flex;align-items:center;gap:7px;text-decoration:none;color:#1e293b;font-size:13px;flex:1;min-width:0;}';
$doc_html .= '.gmdb-file-link:hover{color:#2563eb;}';
$doc_html .= '.gmdb-file-link span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}';
$doc_html .= '.gmdb-icon{font-size:14px;flex-shrink:0;}';
$doc_html .= '.gmdb-ext-link{display:inline-block;padding:2px 9px;border-radius:4px;background:#eff6ff;color:#2563eb;font-size:12px;font-weight:700;text-decoration:none;flex-shrink:0;margin-left:8px;}';
$doc_html .= '.gmdb-ext-link:hover{background:#2563eb;color:#fff;}';
$doc_html .= '.gmdb-stats{font-size:11px;color:#64748b;margin-top:12px;text-align:right;}';
$doc_html .= '</style>';

$doc_html .= '<div class="gmdb-wrap">';
$doc_html .= '<div class="gmdb-header">';
$doc_html .= '<div class="gmdb-header-title">📂 Acceso a Documentos de la Base de Conocimiento</div>';
$doc_html .= '<div class="gmdb-header-sub">Repositorio: <a href="' . htmlspecialchars($repourl) . '" target="_blank" rel="noopener" class="gmdb-repo-link">' . htmlspecialchars($repourl) . '</a> · Rama: <strong>' . htmlspecialchars($branch_link) . '</strong></div>';
$doc_html .= '</div>';

// Barra de búsqueda y botones toggle all
$doc_html .= '<div class="gmdb-search-bar">';
$doc_html .= '<div class="gmdb-search-input-wrap">';
$doc_html .= '<span class="gmdb-search-icon">🔍</span>';
$doc_html .= '<input type="text" id="gmdb-search-input" class="gmdb-search-input" placeholder="Buscar documento por nombre, ruta o carpeta (ej. campo, ecuaciones, concepts)..." autocomplete="off">';
$doc_html .= '<button type="button" id="gmdb-search-clear" class="gmdb-search-clear" style="display:none;" title="Limpiar búsqueda">✕</button>';
$doc_html .= '</div>';
$doc_html .= '<div class="gmdb-search-actions">';
$doc_html .= '<button type="button" onclick="gmdbToggleAll(true)" class="gmdb-btn-toggle">➕ Abrir todas</button>';
$doc_html .= '<button type="button" onclick="gmdbToggleAll(false)" class="gmdb-btn-toggle">➖ Cerrar todas</button>';
$doc_html .= '</div>';
$doc_html .= '</div>';
$doc_html .= '<div id="gmdb-search-count" class="gmdb-search-count"></div>';

$total_docs = 0;
foreach ($md_by_dir as $dir => $files) {
    $folder_label = ($dir === '/') ? '📁 Raíz del repositorio' : '📁 ' . htmlspecialchars($dir);
    // Por defecto, si la carpeta tiene 8 o menos archivos (o es la raíz), abrimos; si tiene muchos (como okf/concepts), cerrada por defecto para no abrumar.
    $is_default_open = ($dir === '/' || count($files) <= 8);
    $open_attr = $is_default_open ? ' open' : '';
    $default_flag = $is_default_open ? '1' : '0';
    
    $doc_html .= '<details class="gmdb-folder" data-folder="' . htmlspecialchars(strtolower($dir)) . '" data-default-open="' . $default_flag . '"' . $open_attr . '>';
    $doc_html .= '<summary class="gmdb-folder-header">';
    $doc_html .= '<span class="gmdb-folder-title">' . $folder_label . ' <span style="font-weight:400;color:#64748b;">(' . count($files) . ' archivos)</span></span>';
    $doc_html .= '<span class="gmdb-toggle-arrow">▼</span>';
    $doc_html .= '</summary>';
    $doc_html .= '<div class="gmdb-folder-body">';
    foreach ($files as $filepath) {
        $total_docs++;
        $filename = basename($filepath);
        $viewer_url = (new moodle_url('/blocks/gitmetrics/view_file.php', [
            'courseid' => $courseid_for_links,
            'blockid'  => 0,
            'path'     => $filepath,
            'repo_url' => $repourl,
            'branch'   => $branch_link,
        ]))->out();
        $encoded_path = str_replace('%2F', '/', rawurlencode($filepath));
        $external_url = rtrim($repourl, '/') . '/-/blob/' . rawurlencode($branch_link) . '/' . $encoded_path;
        
        $doc_html .= '<div class="gmdb-file-row" data-path="' . htmlspecialchars(strtolower($filepath)) . '" data-name="' . htmlspecialchars(strtolower($filename)) . '">';
        $doc_html .= '<a href="' . $viewer_url . '" class="gmdb-file-link" title="Abrir ' . htmlspecialchars($filename) . ' en Moodle">';
        $doc_html .= '<span class="gmdb-icon">📄</span>';
        $doc_html .= '<span>' . htmlspecialchars($filename) . '</span>';
        $doc_html .= '</a>';
        $doc_html .= '<a href="' . htmlspecialchars($external_url) . '" target="_blank" rel="noopener" class="gmdb-ext-link" title="Ver en GitLab">↗</a>';
        $doc_html .= '</div>';
    }
    $doc_html .= '</div></details>';
}

$doc_html .= '<div class="gmdb-stats">📊 ' . $total_docs . ' documentos Markdown · Cargado desde el repositorio remoto · No se almacena ningún archivo en Moodle</div>';

// Script de búsqueda (Acepta con guión tal y como en el original) y toggle all
$doc_html .= '<script>
function gmdbToggleAll(open) {
  document.querySelectorAll("details.gmdb-folder").forEach(function(d) {
    if (open) d.setAttribute("open", "");
    else d.removeAttribute("open");
  });
}
(function() {
  var input = document.getElementById("gmdb-search-input");
  var clearBtn = document.getElementById("gmdb-search-clear");
  var countEl = document.getElementById("gmdb-search-count");
  if (!input) return;
  
  function doSearch() {
    var q = input.value.trim().toLowerCase();
    if (clearBtn) clearBtn.style.display = q ? "block" : "none";
    if (!q) {
      document.querySelectorAll(".gmdb-file-row").forEach(function(row) { row.style.display = ""; });
      document.querySelectorAll("details.gmdb-folder").forEach(function(folder) {
        folder.style.display = "";
        if (folder.getAttribute("data-default-open") === "1") folder.setAttribute("open", "");
        else folder.removeAttribute("open");
      });
      if (countEl) countEl.style.display = "none";
      return;
    }
    
    var matches = 0;
    document.querySelectorAll("details.gmdb-folder").forEach(function(folder) {
      var folderHasMatch = false;
      folder.querySelectorAll(".gmdb-file-row").forEach(function(row) {
        var path = row.getAttribute("data-path") || "";
        var name = row.getAttribute("data-name") || "";
        if (path.indexOf(q) !== -1 || name.indexOf(q) !== -1) {
          row.style.display = "";
          folderHasMatch = true;
          matches++;
        } else {
          row.style.display = "none";
        }
      });
      if (folderHasMatch) {
        folder.style.display = "";
        folder.setAttribute("open", "");
      } else {
        folder.style.display = "none";
      }
    });
    
    if (countEl) {
      countEl.style.display = "block";
      countEl.innerHTML = matches === 0 ? "❌ No se encontraron archivos coincidentes con <strong>\'" + q + "\'</strong>." : "✅ Encontrados <strong>" + matches + "</strong> archivos coincidentes.";
    }
  }
  
  input.addEventListener("input", doSearch);
  if (clearBtn) {
    clearBtn.addEventListener("click", function() {
      input.value = "";
      doSearch();
      input.focus();
    });
  }
})();
</script>';
$doc_html .= '</div>';

$topics = [
    0 => [
        'name'    => '📂 Acceso a Documentos',
        'summary' => $doc_html
    ],
    1 => [
        'name'    => 'Volumen y Tamaño de la Base de Conocimiento',
        'summary' => $styles . $renderer->render_volume($metrics['volume'])
    ],
    2 => [
        'name'    => 'Red de Enlaces e Interconectividad Markdown',
        'summary' => $renderer->render_network($metrics['network'])
    ],
    3 => [
        'name'    => 'Taxonomía, Metadatos y Etiquetas YAML',
        'summary' => $renderer->render_tags($metrics['tags'])
    ],
    4 => [
        'name'    => 'Calidad Markdown y Elementos Estructurales',
        'summary' => $renderer->render_format($metrics['format'])
    ]
];

require_once($CFG->dirroot . '/course/lib.php');
course_create_sections_if_missing($course, [0, 1, 2, 3, 4]);

foreach ($topics as $num => $data) {
    $sec = $DB->get_record('course_sections', ['course' => $course->id, 'section' => $num]);
    if ($sec) {
        $sec->name = $data['name'];
        $sec->summary = $data['summary'];
        $sec->summaryformat = FORMAT_HTML;
        $sec->timemodified = time();
        $DB->update_record('course_sections', $sec);
    } else {
        $sec = new stdClass();
        $sec->course = $course->id;
        $sec->section = $num;
        $sec->name = $data['name'];
        $sec->summary = $data['summary'];
        $sec->summaryformat = FORMAT_HTML;
        $sec->visible = 1;
        $sec->timemodified = time();
        $DB->insert_record('course_sections', $sec);
    }
}

// Eliminar foro de Avisos/Announcements si se creó por defecto para que no salga en la barra izquierda
$course->newsitems = 0;
$DB->update_record('course', $course);
$cms = get_coursemodules_in_course('forum', $course->id);
foreach ($cms as $cm) {
    course_delete_module($cm->id);
}

// Eliminar secciones sobrantes o vacías mayores que 4 (ej. New section al final)
$extra_sections = $DB->get_records_select('course_sections', "course = ? AND section > 4", [$course->id]);
foreach ($extra_sections as $es) {
    course_delete_section($course, $es, true);
}

rebuild_course_cache($course->id, true);
echo "Los temas de la asignatura se han poblado, se han limpiado avisos/secciones sobrantes y la caché del curso se ha reconstruido con éxito.\n";
