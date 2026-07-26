# Estudio
Esta sección documenta las funciones principales de la herramienta de estudio del plugin Maubot.
Los fragmentos de código se extraen directamente de `estudio.py` usando marcadores de sección, de modo que la documentación siempre refleje el código real.

### 1. Generación de Flashcards y Ejercicios
Transforma fragmentos documentales aleatorios en preguntas directas de memorización activa, y modela problemas y resolución paso a paso.
```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/estudio.py:flashcards"
```
### 2. Técnica Feynman
Valida explicaciones en texto libre emitidas por el alumno para identificar lagunas conceptuales (`evaluar_respuesta`). Toda la evaluación se apoya en un contexto dinámico descargado de la Base de Conocimientos (BdC) en Git para garantizar respuestas basadas en el material oficial del estudiante.
```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/estudio.py:evaluar"
```
### 3. Resumen de Sesión
Genera informes con métricas a partir del log de actividad (`db.py`).
```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/estudio.py:resumen"
```