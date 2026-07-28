# student_progress.php

Ubicación: `gitmetrics/classes/student_progress.php`

Cliente HTTP que consume el endpoint de progreso del bot Maubot y cachea los resultados en la tabla `block_gitmetrics_progress_cache` de la BD de Moodle.

## Decisión de arquitectura: opción (b) — endpoint HTTP

Se eligió la opción (b) frente a la conexión directa a PostgreSQL por tres razones:

1. **El driver pgsql no está disponible** en el contenedor `moodle-app` (imagen Bitnami) sin modificar el Dockerfile, lo que añade fragilidad al despliegue.
2. **Desacoplamiento de esquemas**: si la BD del bot cambia, sólo cambia el endpoint; el plugin PHP no requiere recompilarse.
3. **Seguridad**: el endpoint sólo expone los campos necesarios para el panel del profesor (`id_pseudo`, `num_sesiones`, `ultima_sesion`, `ultimo_resumen`, `conceptos_dominados`) sin revelar el Matrix ID de los alumnos.

El token de autenticación sigue el mismo patrón que `gitlab_token`/`github_token` ya gestionados en `base-config.yaml`.

## Configuración necesaria (Ajustes globales de Moodle)

| Clave de configuración | Descripción |
|---|---|
| `block_gitmetrics/bot_progress_url` | URL base del endpoint (p. ej. `http://maubot:29316/_maubot/plugin/progress`) |
| `block_gitmetrics/bot_progress_token` | Token Bearer que autentica las peticiones |

## Formato del endpoint esperado

```
GET <bot_progress_url>/progreso?curso_id=<n>
Authorization: Bearer <token>
→ 200 OK, Content-Type: application/json

[
  {
    "id_pseudo": "uuid-del-alumno",
    "curso_id": 42,
    "num_sesiones": 7,
    "ultima_sesion": 1753574400,
    "ultimo_resumen": "El alumno repasó integrales y tuvo dificultades con...",
    "conceptos_dominados": 12
  },
  ...
]
```

## Código Fuente

```php
--8<-- "gitmetrics/classes/student_progress.php:class_desc"
```

### Obtener progreso (con caché)

```php
--8<-- "gitmetrics/classes/student_progress.php:get_progress"
```

### Llamada al endpoint del bot

```php
--8<-- "gitmetrics/classes/student_progress.php:fetch_from_bot"
```

### Caché en BD de Moodle

```php
--8<-- "gitmetrics/classes/student_progress.php:cache"
```

### Datos para el panel de gestión del profesor

Agrupa los datos del repositorio base del curso, los profesores colaboradores, el estado de los forks de cada estudiante (`block_gitmetrics_student_fork`) y el progreso extraído del bot para presentarlos de forma centralizada al docente.

```php
--8<-- "gitmetrics/classes/student_progress.php:get_management_data"
```
