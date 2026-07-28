# constants.py

Ubicación: `maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/constants.py`

Constantes de configuración centralizadas del plugin.

| Constante | Valor | Uso |
|---|---|---|
| `PENDIENTE_TTL_SEGUNDOS` | 1800 s (30 min) | TTL de confirmaciones de subida pendientes |
| `CONFIRMACION_BORRADO_TTL_SEGUNDOS` | 300 s (5 min) | TTL de confirmaciones de borrado |
| `SESION_VENTANA_SEGUNDOS` | 10 800 s (3 h) | Ventana de `!resumen` **bajo demanda** — **no tocar** |
| `SESION_INACTIVIDAD_SEGUNDOS` | 1800 s (30 min) | Umbral de inactividad para cierre automático de sesión |
| `SESION_DETECTOR_INTERVALO_SEGUNDOS` | 600 s (10 min) | Frecuencia del detector de inactividad en `sesiones.py` |
| `RETENTION_DAYS_DEFAULT` | 365 días | Días de retención por defecto si no hay valor en `base-config.yaml` |
| `MAX_CONCEPTOS_REPASO_TEMA` | 25 | Máximo de conceptos por sesión de `!repasartema` |
| `MAX_CONCURRENCIA_GITHUB` | 5 | Límite de peticiones simultáneas a GitHub/GitLab |

> [!NOTE]
> `SESION_VENTANA_SEGUNDOS` y `SESION_INACTIVIDAD_SEGUNDOS` son valores distintos con propósitos distintos. El primero define la ventana de búsqueda de `!resumen` (comando bajo demanda, sin persistencia). El segundo controla cuándo el detector automático cierra una sesión y persiste su resumen.

## Código Fuente

```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/constants.py"
```
