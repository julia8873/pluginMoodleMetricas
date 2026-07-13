<?php
defined('MOODLE_INTERNAL') || die();

// Moodle busca la clase con el nombre: {componente}_renderer
// Por eso NO usamos namespace aquí.

class block_holamundo_renderer extends plugin_renderer_base {

    public function render_saludo($nombre, $contador) {
        $html  = html_writer::tag('div', 'Hola ' . $nombre, ['class' => 'holamundo-saludo']);
        $html .= html_writer::tag('small', get_string('contadortexto', 'block_holamundo', $contador));
        return $html;
    }
}