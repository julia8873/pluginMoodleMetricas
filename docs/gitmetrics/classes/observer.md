# observer.php

Ubicación: `gitmetrics/classes/observer.php`

Manejador de eventos de Moodle (observers) que conecta las acciones del LMS con el aprovisionamiento de infraestructura en Matrix y en el proveedor de repositorios Git (GitHub/GitLab).

## Funciones Principales

1. **`course_created`**: Asegura la creación de la sala en Matrix/Element y la incorporación del bot LLM Wiki Assistant cuando se crea un nuevo curso en Moodle.
2. **`teacher_assigned`**: Automatiza el aprovisionamiento del repositorio del curso a partir de la plantilla base cuando se asigna el rol de profesor (`editingteacher`). Además, añade a dicho profesor como colaborador (`maintainer` / `maintain`) al repositorio recién creado o ya existente.
   - *Nota de concurrencia:* Si se matricula un segundo (o subsecuente) profesor en el mismo curso, este método detecta que el repositorio ya existe (status = `creado`) y omite la fase de aprovisionamiento, limitándose a enviar la invitación como colaborador al nuevo profesor. Esta idempotencia garantiza la resiliencia del proceso.

3. **`student_enrolled`**: Gestiona la creación de un fork personal del repositorio de la Base de Conocimiento del curso para cada estudiante, disparado mediante la asignación del rol de estudiante.
   - *Nota sobre eventos y roles:* Moodle dispara el evento de creación de matrícula (`user_enrolment_created`) antes de asignar el rol al usuario, lo que imposibilita filtrar por el rol de estudiante en ese instante. Por ello, este método está enganchado al evento `\core\event\role_assigned`, filtrando explícitamente el rol `student`.
   - *Nota sobre identificadores:* Genera un UUID estándar (v4) para el `id_pseudo` del estudiante, utilizando el mismo formato subyacente que `db.py` del bot (UUID), asegurando compatibilidad cruzada sin exponer IDs reales.
   - *Nota sobre GitHub API:* GitHub restringe forjear un repositorio a la misma cuenta propietaria original. Para sortear esto, `fork_repo` transitoriamente convierte el repositorio original en plantilla (template) para efectuar la copia exacta sin restricciones.

## Requisitos de Configuración

Para que el aprovisionamiento de repositorios funcione correctamente mediante `teacher_assigned`, se requiere configurar las credenciales en los ajustes del bloque (`block_gitmetrics`):

- `template_owner`: El usuario/organización dueña del repositorio plantilla.
- `template_repo`: El nombre del repositorio plantilla (ej: `BdC-template`).
- `template_provider`: El proveedor de la plantilla (`github` o `gitlab`).
- `target_namespace`: (Opcional) El namespace destino donde se creará el repositorio del curso. Si se omite, se usa el `template_owner`.

El token de acceso correspondiente (`github_token` o `gitlab_token`) debe poseer privilegios de creación de repositorios y gestión de colaboradores.

## Código Fuente

### Manejo de asignación de profesor (Aprovisionamiento del Repo)

```php
--8<-- "gitmetrics/classes/observer.php:teacher_assigned"
```

### Manejo de asignación de estudiante (Aprovisionamiento de Fork)

```php
--8<-- "gitmetrics/classes/observer.php:student_enrolled"
```
