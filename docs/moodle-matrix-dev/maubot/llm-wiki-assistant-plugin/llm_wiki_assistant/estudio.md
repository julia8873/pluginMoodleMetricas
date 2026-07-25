# Herramientas de Estudio (`estudio.py`)

Ubicación: `maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/estudio.py`

Este módulo desacopla por completo la lógica cognitiva y los prompts (las peticiones al LLM) de las mecánicas de chat. 

## Arquitectura

```python
"""
Herramientas de estudio: flashcards, ejercicios, técnica Feynman, preguntas de
concepto, búsqueda de ejercicios por técnica y resumen de sesión.

Se mantiene aparte de bot.py por lo mismo que pdf_ingest.py e image_ocr.py:
aquí solo hay "qué preguntarle al LLM y cómo interpretar su respuesta", sin
nada de Matrix/GitHub, para poder cambiar los prompts sin tocar el resto del bot.
"""

import asyncio
import math
import re

from .llm_provider import LLMProvider
```


## Funciones Principales
1. **Generación de Flashcards**: Transforma fragmentos documentales aleatorios en preguntas directas de memorización activa.
2. **Generación de Ejercicios**: Modela problemas y resolución paso a paso.
3. **Técnica Feynman**: Valida explicaciones en texto libre emitidas por el alumno para identificar lagunas conceptuales.
4. **Resumen de Sesión**: Genera informes con métricas a partir del log de actividad (`db.py`).

Toda la evaluación (`evaluar_respuesta`) se apoya en un contexto dinámico descargado de la Base de Conocimientos (BdC) en GitHub para garantizar respuestas basadas en el material oficial del estudiante.
