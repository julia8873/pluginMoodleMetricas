# db.py

Ubicación: `maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/db.py`

Gestor de persistencia de trazabilidad del estudiante.  
Usa la base de datos **PostgreSQL (asyncpg)** que maubot proporciona automáticamente a cada plugin a través de `self.database` cuando `database: true` está declarado en `maubot.yaml`.  
No se trata de SQLite: el plugin usa `database_type: asyncpg` y la BD real de Postgres del stack Docker.

> [!NOTE]
> El `student_id` de todas las tablas es el **Matrix ID** del usuario (p. ej. `@julia:mi-matrix-local.dev`). La tabla `estudiantes` (añadida en `upgrade_v7`) mapea ese ID a un UUID pseudónimo (`id_pseudo`) que es el único identificador que se expone al panel del profesor vía Moodle.

## Migraciones de esquema

| Versión | Descripción |
|---|---|
| v1 | `interacciones`, `fuentes_raw`, `ejercicios` |
| v2 | Columna `tipo` en `ejercicios` |
| v3 | `conceptos` (dominio por concepto) |
| v4 | `curaciones` (subidas/movidos/borrados a la BdC) |
| v5 | `qa_historial` (preguntas, respuestas, evaluaciones) |
| v6 | Dummy (evita error de versión adelantada) |
| **v7** | `estudiantes` (pseudonimización), `sesiones`, `resumenes_sesion`; columna `session_id` en `interacciones` y `qa_historial` |

## Métodos de sesión añadidos en v7

- `ensure_estudiante(student_id)` — lazy insert del alumno la primera vez que se le ve; devuelve su `id_pseudo`.
- `crear_o_continuar_sesion(student_id, room_id)` — devuelve el `session_id` activo o crea uno nuevo.
- `incrementar_eventos_sesion(session_id)` — actualiza el contador de eventos de la sesión.
- `cerrar_sesion(session_id)` — fija el campo `fin` a `now()`.
- `guardar_resumen_sesion(session_id, texto, ...)` — persiste el resumen generado al cerrar.
- `obtener_sesiones_abiertas_inactivas(umbral_segundos)` — para el detector de `sesiones.py`.
- `obtener_interacciones_sesion(session_id)` — interacciones de una sesión, orden cronológico.
- `obtener_progreso_para_moodle(curso_id)` — datos para el panel del profesor (pseudonimizados).
- `purgar_datos_antiguos(retention_days)` — borra `interacciones`/`qa_historial` antiguos; conserva `resumenes_sesion`.

## Código Fuente

```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/db.py:file_desc"
```
