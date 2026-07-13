<?php
defined('MOODLE_INTERNAL') || die();

// Clase que conecta todo

class block_holamundo extends block_base {

    public function init() {
        $this->title = get_string('pluginname', 'block_holamundo');
    }

    // decirle a moodle que tenemos un fichero settings.php
    public function has_config() {
        return true; 
    }

    public function get_content() {
        global $DB;

        if ($this->content !== null) {
            return $this->content;
        }

        // nombre: instancia > global > 'Mundo'.
        // NOTA: Moodle elimina el prefijo 'config_' al guardar → el campo 'config_nombre' se lee como 'nombre'
        $nombreinstancia = !empty($this->config->nombre) ? $this->config->nombre : '';
        $nombreglobal = get_config('block_holamundo', 'nombredefecto');
        // si hay nombre instancia, sino mirar si hay nombre gobal, sino por defecto 'Mundo'
        $nombre = !empty($nombreinstancia) ? $nombreinstancia : ($nombreglobal ?: 'Mundo');

        // Actualizar contador de visitas en la tabla propia.
        $registro = $DB->get_record('block_holamundo_visitas', ['blockinstanceid' => $this->instance->id]);
        if ($registro) {
            $registro->contador++;
            $registro->timemodified = time();
            $DB->update_record('block_holamundo_visitas', $registro);
        } else {
            $registro = new stdClass();
            $registro->blockinstanceid = $this->instance->id;
            $registro->contador = 1;
            $registro->timemodified = time();
            $DB->insert_record('block_holamundo_visitas', $registro);
        }

        // Delegar el HTML al renderer.
        $renderer = $this->page->get_renderer('block_holamundo');
        $this->content = new stdClass();
        $this->content->text = $renderer->render_saludo($nombre, $registro->contador);
        $this->content->footer = '';

        return $this->content;
    }
}