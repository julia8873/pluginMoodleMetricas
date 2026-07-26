# Gestión de Usuarios (Scripts CLI)

Ubicación: `usuarios/`

Dentro de este directorio se encuentran scripts para crear y matricular cuentas de prueba (alumno, profesor) de manera rápida en Moodle sin tener que pasar por la interfaz gráfica.

## `crear_usuarios.php`

Este script se encarga de dar de alta varios perfiles simulados (Profesor, Alumno 1, Alumno 2).

```php
--8<-- "moodle-matrix-dev/usuarios/crear_usuarios.php:file_desc"
```


## `matricular_usuarios.php`

Este script asocia los usuarios generados previamente al curso corto 'AA'.

```php
--8<-- "moodle-matrix-dev/usuarios/matricular_usuarios.php:file_desc"
```
