# Core: GithubBot (`bot.py`)

Ubicación: `github-bot-plugin/github-bot-plugin/github_bot/bot.py`

El archivo `bot.py` orquesta la interacción entre el usuario (vía Matrix), la base de conocimientos (vía GitHub) y el motor de estudio.

## Descripción General

```python
--8<-- "moodle-matrix-dev/github-bot-plugin/github-bot-plugin/github_bot/bot.py:file_desc"
```

## Diagrama de Interacción de Mensajes

```mermaid
graph TD
    A[Mensaje entrante en Matrix] --> B{¿Es un adjunto?}
    B -->|Sí (Imagen / PDF)| C[Proceso de Ingesta]
    C --> D[OCR / PyPDF / Gemini Vision]
    D --> E[Subir a GitHub raw/ y okf/]
    B -->|No| F{¿Es un comando ! ?}
    F -->|Sí| G[Delegar a handlers estudio.py / bd.py]
    F -->|No| H{¿Hay estado pendiente?}
    H -->|Sí| I[Responder a flashcard / Ejercicio]
    H -->|No| J[Ignorar]
```

## Ciclo de Vida y Concurrencia

El bot implementa un control de caché agresivo y manejo asíncrono avanzado con semáforos (`MAX_CONCURRENCIA_GITHUB`) para no exceder las cuotas de la API del proveedor (GitHub/GitLab) ni solapar transacciones concurrentes en el chat (`_user_locks`).
