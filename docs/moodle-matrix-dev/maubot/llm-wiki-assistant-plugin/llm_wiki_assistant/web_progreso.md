# web_progreso.py

Ubicación: `maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/web_progreso.py`

Mixin que expone el endpoint HTTP nativo `GET /progreso` usando la API de web handlers de Maubot (`@web.get`, módulo `maubot.handlers.web`). No requiere ningún microservicio separado.

> [!IMPORTANT]
> Requiere `webapp: true` en `maubot.yaml` (ya añadido). La URL del endpoint sigue el patrón nativo de Maubot:
> ```
> http://<maubot-host>/_matrix/maubot/plugin/<instance_id>/progreso
> ```
> La URL exacta de la instancia desplegada está disponible en `self.webapp_url` y aparece en el log de arranque del bot.

## Autenticación

El endpoint usa un **token Bearer** compartido entre el bot y Moodle:

- **Bot** (`base-config.yaml`): `progress_api_token: "tu-secreto-aqui"`
- **Moodle** (Ajustes globales del plugin): `bot_progress_token = "tu-secreto-aqui"`

Para generar un token seguro:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Parámetros

| Parámetro | Tipo | Descripción |
|---|---|---|
| `curso_id` (query, opcional) | entero | Filtra resultados al curso indicado. Sin él, devuelve todos los alumnos. |

## Respuesta

```json
[
  {
    "id_pseudo":           "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    "curso_id":            42,
    "num_sesiones":        7,
    "ultima_sesion":       1753574400,
    "ultimo_resumen":      "El alumno repasó integrales y mostró dificultades con...",
    "conceptos_dominados": 12
  }
]
```

> [!NOTE]
> `id_pseudo` es el UUID interno del alumno — nunca el Matrix ID. Esta pseudonimización es obligatoria antes de exponer datos al panel del profesor (RGPD art. 5.1.c, minimización de datos).

## Códigos de respuesta

| Código | Causa |
|---|---|
| `200` | OK, array de filas (puede ser vacío) |
| `400` | `curso_id` no es un entero válido |
| `401` | Token ausente, malformado o incorrecto — o `progress_api_token` no configurado |
| `500` | Error al consultar la BD |

## Código Fuente

```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/web_progreso.py:file_desc"
```

### Handler

```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/web_progreso.py:handler"
```
