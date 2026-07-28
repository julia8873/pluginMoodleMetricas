# Sesiones y Panel del Profesor — Decisiones de Arquitectura

> [!IMPORTANT]
> Este documento recoge las decisiones de diseño del sistema de sesiones automáticas, el puente hacia Moodle y la política de retención/pseudonimización. Debe leerse antes de tocar cualquier fichero relacionado.

---

## 1. Criterio de cierre de sesión

Una **sesión de chat** agrupa las interacciones (`interacciones`, `qa_historial`) de un mismo estudiante en una sala Matrix mientras hay actividad continua. Se cierra automáticamente por inactividad.

**Umbral**: `SESION_INACTIVIDAD_SEGUNDOS = 1800` (30 minutos, configurable vía `session_inactivity_seconds` en `base-config.yaml`).  
**Detección**: la tarea periódica `_detector_inactividad` de `sesiones.py` comprueba cada 10 minutos (`SESION_DETECTOR_INTERVALO_SEGUNDOS`) qué sesiones llevan más de 30 minutos sin ninguna interacción vinculada por `session_id`.

### ¿Por qué 30 minutos?

- Es el umbral habitual en analítica de aprendizaje (LAK/xAPI) para separar "sesiones de trabajo" distintas.
- Evita cortar sesiones por interrupciones breves (mensajes del sistema, pausas para pensar).
- Es suficientemente conservador para no generar cientos de sesiones de 2 minutos que inflen el historial.

### Ciclo de vida de una sesión

```
Nuevo mensaje del alumno
  └── ¿Hay sesión abierta en esa sala?
        ├── SÍ → se reutiliza el session_id existente
        └── NO → Tracker.crear_o_continuar_sesion() → nuevo UUID

Cada 10 min (tarea periódica):
  └── Sesión sin actividad > 30 min
        ├── generar_resumen_sesion() (misma función que !resumen)
        ├── Tracker.guardar_resumen_sesion()  ← persiste el resumen
        └── Tracker.cerrar_sesion()           ← fija campo "fin"
```

`!resumen` (comando bajo demanda) **no se toca**: sigue usando la ventana fija de 3 horas (`SESION_VENTANA_SEGUNDOS`) sin persistir nada, tal como estaba antes.

---

## 2. Puente hacia Moodle: opción elegida — (b) Endpoint HTTP

### Las dos opciones evaluadas

| | Opción (a) — Conexión directa a PostgreSQL | Opción (b) — Endpoint HTTP del bot |
|---|---|---|
| **Driver requerido en PHP** | `pgsql` (no incluido en Bitnami) | Ninguno adicional (`curl` ya disponible) |
| **Acoplamiento de esquemas** | Alto: PHP debe conocer el esquema interno del bot | Bajo: el endpoint es un contrato estable |
| **Datos expuestos** | Todos los campos de la BD del bot | Sólo los campos elegidos explícitamente |
| **Autenticación** | Credenciales de BD en config de Moodle | Token Bearer (mismo patrón que git tokens) |
| **Mantenimiento** | Rompe si el esquema del bot cambia | Sólo cambia el endpoint si el esquema cambia |

### Justificación de (b)

La imagen Bitnami de Moodle (`bitnami/moodle`) no incluye la extensión `pgsql` de PHP. Añadirla requiere un `Dockerfile` personalizado y complica el mantenimiento del stack. El endpoint HTTP, en cambio, sólo necesita que el contenedor `maubot` sea accesible desde `moodle-app` en la red Docker interna, lo que ya ocurre.

El endpoint devuelve exclusivamente `id_pseudo` (UUID), nunca el Matrix ID del alumno, alineándose con el principio de minimización de datos (RGPD art. 5.1.c).

### Implementación

- **Bot (Python)** — `web_progreso.py`:  
  El plugin usa `webapp: true` en `maubot.yaml` y decora el handler con `@web.get("/progreso")` (módulo `maubot.handlers.web`). La URL resultante sigue el patrón nativo de Maubot:  
  ```
  http://<maubot-host>/_matrix/maubot/plugin/<instance_id>/progreso
  ```
  La URL exacta está disponible en `self.webapp_url` dentro del plugin y aparece en el log de arranque. El handler llama a `Tracker.obtener_progreso_para_moodle(curso_id)` y devuelve un array JSON.  
  Ver documentación detallada en [web_progreso.md](llm_wiki_assistant/web_progreso.md).

- **Moodle (PHP)** — `block_gitmetrics\student_progress` en `gitmetrics/classes/student_progress.php`:  
  Consume el endpoint y cachea los datos en `block_gitmetrics_progress_cache`. El administrador rellena `bot_progress_url` en los ajustes del plugin con la URL `self.webapp_url` del bot.

### Configuración del token

```bash
# Generar un secreto aleatorio seguro
python3 -c "import secrets; print(secrets.token_hex(32))"
```

- En `base-config.yaml` del bot: `progress_api_token: "<secreto>"`
- En los ajustes de Moodle (Admin > Plugins > Blocks > Git KB Metrics): `bot_progress_token = "<secreto>"`

---

## 3. Política de retención y pseudonimización

### Pseudonimización

La tabla `estudiantes` mapea cada `student_id` (Matrix ID, p. ej. `@julia:mi-matrix-local.dev`) a un `id_pseudo` (UUID v4 generado en el primer login). Este UUID es el único identificador que sale de la BD del bot hacia Moodle. Ni el Matrix ID ni ningún dato que permita identificar directamente al alumno se transmite al plugin PHP.

El `id_pseudo` puede asociarse a un `moodle_user_id` y `curso_id` opcionalmente (p. ej. si el administrador lo rellena manualmente o por un proceso de sincronización futura).

### Retención

| Tabla | Política |
|---|---|
| `interacciones` | Se purgan tras `retention_days` días (defecto: 365). Job diario en `sesiones.py`. |
| `qa_historial` | Ídem. |
| `resumenes_sesion` | **No se purgan**: actúan como registro agregado de largo plazo. |
| `conceptos`, `curaciones`, `fuentes_raw` | No afectadas por la purga actual (su volumen es bajo y no contienen texto libre de actividad). |

### Aviso legal RGPD/LOPDGDD

> [!CAUTION]
> La UGR es una **universidad pública española** y está obligada por el **art. 34 de la LOPDGDD** a designar un **Delegado de Protección de Datos (DPD)**. Antes de desplegar este sistema con alumnos reales, el DPD de la UGR debe:
>
> - Revisar y aprobar la política de retención (`retention_days`).
> - Verificar que la pseudonimización mediante `id_pseudo` es suficiente o si se requiere anonimización plena.
> - Asegurarse de que los alumnos reciben información sobre el tratamiento de sus datos de actividad (arts. 13-14 RGPD).
> - Evaluar si se necesita una EIPD (Evaluación de Impacto) según el art. 35 RGPD (tratamiento sistemático de datos de rendimiento de personas físicas en el ámbito educativo).
