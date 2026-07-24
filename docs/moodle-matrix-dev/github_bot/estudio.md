# Herramientas de Estudio (`estudio.py`)

Ubicación: `github-bot-plugin/github-bot-plugin/github_bot/estudio.py`

Este módulo desacopla por completo la lógica cognitiva y los prompts (las peticiones al LLM) de las mecánicas de chat. 

## Arquitectura

```python
--8<-- "moodle-matrix-dev/github-bot-plugin/github-bot-plugin/github_bot/estudio.py:file_desc"
```

## Funciones Principales
1. **Generación de Flashcards**: Transforma fragmentos documentales aleatorios en preguntas directas de memorización activa.
2. **Generación de Ejercicios**: Modela problemas y resolución paso a paso.
3. **Técnica Feynman**: Valida explicaciones en texto libre emitidas por el alumno para identificar lagunas conceptuales.
4. **Resumen de Sesión**: Genera informes con métricas a partir del log de actividad (`db.py`).

Toda la evaluación (`evaluar_respuesta`) se apoya en un contexto dinámico descargado de la Base de Conocimientos (BdC) en GitHub para garantizar respuestas basadas en el material oficial del estudiante.
