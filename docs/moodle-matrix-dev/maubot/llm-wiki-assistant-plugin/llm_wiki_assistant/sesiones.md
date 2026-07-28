# sesiones.py

Ubicación: `maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/sesiones.py`

Módulo de gestión automática del ciclo de vida de sesiones de estudio.  
Arranca dos tareas `asyncio` periódicas desde `bot.py::start()`:

| Tarea | Intervalo | Función |
|---|---|---|
| `_detector_inactividad` | 10 min (`SESION_DETECTOR_INTERVALO_SEGUNDOS`) | Cierra sesiones sin actividad > 30 min y genera+persiste su resumen |
| `_job_purga` | 24 h | Borra filas de `interacciones`/`qa_historial` más antiguas que `retention_days` |

> [!IMPORTANT]
> `_detector_inactividad` reutiliza `generar_resumen_sesion()` de `estudio.py` — la misma función que usa `!resumen`. La diferencia es que aquí el resultado se guarda en `resumenes_sesion` con `Tracker.guardar_resumen_sesion()`, y la ventana es la sesión real (no la ventana fija de 3 h de `!resumen`).

> [!WARNING]
> El job de purga borra datos personales de forma irreversible. Revisar con el DPD de la UGR antes de activar en producción con alumnos reales (**RGPD art. 5.1.e**, **LOPDGDD art. 34** — la UGR está obligada a designar DPD como universidad pública).

## Flujo del detector de inactividad

```
cada 10 min:
  sesiones = Tracker.obtener_sesiones_abiertas_inactivas(1800)
  para cada sesión:
    interacciones = Tracker.obtener_interacciones_sesion(session_id)
    resumen = generar_resumen_sesion(interacciones, contexto_bdc, llm)
    Tracker.guardar_resumen_sesion(session_id, resumen)
    Tracker.cerrar_sesion(session_id)
```

## Código Fuente

```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/sesiones.py:file_desc"
```

### Tarea de detección de inactividad

```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/sesiones.py:detector_inactividad"
```

### Job de purga

```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/sesiones.py:job_purga"
```
