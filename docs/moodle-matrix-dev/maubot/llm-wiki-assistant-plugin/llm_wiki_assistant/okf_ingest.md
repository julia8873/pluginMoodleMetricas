# Ingesta Automática (`okf_ingest.py` y OCR)

Ubicación: `maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/okf_ingest.py`

Cuando un estudiante sube materiales (PDFs o fotografías), el sistema activa pipelines de procesamiento para transformarlos en conocimiento útil (Formato OKF - Open Knowledge Format).

## Descripción de Ingesta (OKF)

```python
"""
Ingesta automática OKF: convierte una fuente recién subida a raw/ en páginas
estructuradas dentro de okf/ (conceptos, entidades, fuentes), siguiendo las
reglas definidas en AGENTS.md del propio repo de la BdC.

Se mantiene aparte de bot.py por lo mismo que estudio.py y pdf_ingest.py: aquí
solo hay "qué pedirle al LLM y cómo interpretar su respuesta", sin nada de
Matrix ni de la API de GitHub, para poder ajustar el prompt sin tocar el resto
del bot.

IMPORTANTE: AGENTS.md se lee en vivo del repo en cada ingesta (con caché TTL,
igual que la documentación de estudio) en vez de copiarse aquí como texto fijo.
Así, si el equipo (Alberto, Jose, Manuel, Incho...) ajusta las convenciones del
wiki en AGENTS.md, la ingesta automática las respeta sin tener que tocar código.
"""

import json
import re
```


## Flujo de Procesamiento

```mermaid
graph TD
    A["Recepción Adjunto"] --> B{"Formato"}
    B -->|"Imagen"| C["OCR Visual Gemini"]
    B -->|"PDF"| D["PyPDF Básico"]
    D --> E{"¿Calidad Pobre?"}
    E -->|"Sí"| F["Sugerir OCR Visual PDF"]
    F --> C
    E -->|"No"| G["Texto Extraído"]
    C --> G
    G --> H["Guardado en carpeta raw/ GitHub"]
    H --> I["Disparo Ingesta OKF automática"]
    I --> J["Estructurar en okf/concepts, okf/entities"]
```

El módulo `okf_ingest.py` lee dinámicamente las reglas del repositorio remoto (`AGENTS.md`) para estructurar los contenidos, mientras que los módulos auxiliares (`pdf_ingest.py` e `image_ocr.py`) manejan las dependencias específicas de visión artificial y extracción binaria.

## Funciones Principales (`okf_ingest.py`)

A continuación se documentan las funciones internas del módulo y su implementación:

### `construir_prompt_ingest`
Construye la instrucción (system prompt) global para que el LLM ejecute la operación INGEST completa sobre una fuente concreta (normalmente archivos cortos).
```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/okf_ingest.py:construir_prompt_ingest"
```

### `dividir_en_lotes`
Divide el texto de un archivo extenso en bloques (lotes), manteniendo un solapamiento de líneas para no cortar conceptos a mitad de párrafo, preparándolo para una ingesta iterativa.
```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/okf_ingest.py:dividir_en_lotes"
```

### `construir_prompt_ingest_lote`
Construye el prompt para procesar de forma exhaustiva un lote específico de un documento largo.
```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/okf_ingest.py:construir_prompt_ingest_lote"
```

### `parsear_respuesta_ingest`
Interpreta, limpia y valida el JSON devuelto por el LLM tras ejecutar INGEST. Comprueba las rutas, el formato de los ficheros y levanta `IngestError` si detecta problemas o posibles escrituras fuera de `okf/`.
```python
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/okf_ingest.py:parsear_respuesta_ingest"
```
