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

# --------------------------------------------------------------------
# Errores
# --------------------------------------------------------------------

class IngestError(Exception):
    """Se lanza cuando el LLM no devuelve la respuesta de INGEST con el formato esperado."""


# --------------------------------------------------------------------
# Construcción del prompt
# --------------------------------------------------------------------

# Quita ```json / ``` si el modelo envuelve el JSON en un bloque de código a
# pesar de que se le pide explícitamente que no lo haga. Es el mismo tipo de
# tolerancia que ya aplica llm_provider.py con el razonamiento de <think>.
_PATRON_FENCE_JSON = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def construir_prompt_ingest(agents_md: str, ruta_fuente_repo: str, nombre_fichero: str, timestamp_iso: str) -> str:
    """
    Construye la instrucción (system prompt) para que el LLM ejecute la
    operación INGEST de AGENTS.md sobre una fuente concreta. El contenido de
    la fuente en sí se pasa como `contexto` a LLMProvider.generar_texto(),
    no aquí, para no mezclar "reglas" con "material a procesar".
    """
    return (
        "Eres el agente LLM que mantiene esta wiki OKF v0.1. A continuación tienes el "
        "fichero AGENTS.md completo del repositorio, con las convenciones e instrucciones "
        "que debes seguir al pie de la letra:\n\n"
        f"--- INICIO AGENTS.md ---\n{agents_md}\n--- FIN AGENTS.md ---\n\n"
        f"Ejecuta la operación INGEST sobre el fichero ya subido en `{ruta_fuente_repo}` "
        f"(nombre original: «{nombre_fichero}»). El contenido de ese fichero se te da a "
        "continuación como CONTENIDO A INGESTAR.\n\n"
        "Sigue los pasos de la operación INGEST de AGENTS.md: crea/actualiza okf/sources/, "
        "okf/concepts/ y okf/entities/ según corresponda, añade cross-links relativos "
        "[[ruta/nombre|Título]] entre páginas relacionadas, y marca con ⚠️ cualquier "
        "afirmación que contradiga contenido que ya conozcas por AGENTS.md o por el propio "
        "material. Respeta el frontmatter obligatorio y las convenciones de nombres, idioma "
        "y longitud de página descritas en AGENTS.md.\n\n"
        f"Usa exactamente este timestamp en el frontmatter de cada fichero: {timestamp_iso}\n\n"
        "NO toques okf/index.md: se gestiona aparte.\n\n"
        "Responde ÚNICAMENTE con un objeto JSON válido (sin bloques de código, sin texto "
        "antes ni después), con esta forma exacta:\n"
        "{\n"
        '  "ficheros": [\n'
        '    {"path": "okf/sources/nombre.md", "contenido": "---\\ntype: Source\\n...---\\n\\n..."}\n'
        "  ],\n"
        '  "log_entry": "## [YYYY-MM-DD] ingest | nombre-fichero\\n\\nResumen breve de lo añadido.",\n'
        '  "contradicciones": ["Descripción breve de cada contradicción detectada, si hay alguna"],\n'
        '  "preguntas_seguimiento": ["Pregunta 1", "Pregunta 2", "Pregunta 3"]\n'
        "}\n\n"
        "Cada \"path\" debe empezar por \"okf/\" (okf/sources/, okf/concepts/ u okf/entities/). "
        "\"ficheros\" debe incluir el fichero de okf/sources/ correspondiente a esta fuente "
        "como mínimo. Si no hay contradicciones o preguntas de seguimiento, usa listas vacías."
    )


# --------------------------------------------------------------------
# Parseo de la respuesta
# --------------------------------------------------------------------

def parsear_respuesta_ingest(texto: str) -> dict:
    """
    Interpreta el JSON devuelto por el LLM tras ejecutar INGEST. Lanza
    IngestError con un mensaje claro si el formato no es el esperado, para
    que bot.py pueda avisar al estudiante sin haber tocado GitHub todavía.
    """
    if not texto or not texto.strip():
        raise IngestError("El modelo ha devuelto una respuesta vacía.")

    texto_limpio = _PATRON_FENCE_JSON.sub("", texto.strip()).strip()

    try:
        datos = json.loads(texto_limpio)
    except json.JSONDecodeError as exc:
        raise IngestError(f"La respuesta del modelo no es JSON válido: {exc}") from exc

    if not isinstance(datos, dict):
        raise IngestError("La respuesta del modelo no es un objeto JSON.")

    ficheros = datos.get("ficheros")
    if not isinstance(ficheros, list) or not ficheros:
        raise IngestError("La respuesta no incluye ningún fichero en 'ficheros'.")

    ficheros_normalizados = []
    for f in ficheros:
        if not isinstance(f, dict):
            raise IngestError("Cada elemento de 'ficheros' debe ser un objeto con 'path' y 'contenido'.")
        path = (f.get("path") or "").strip()
        contenido = f.get("contenido")
        if not path or not isinstance(contenido, str) or not contenido.strip():
            raise IngestError("Cada fichero necesita 'path' y 'contenido' no vacíos.")
        if not path.startswith("okf/"):
            raise IngestError(f"Ruta fuera de okf/: '{path}'. Se descarta la ingesta completa por seguridad.")
        if ".." in path:
            raise IngestError(f"Ruta sospechosa (contiene '..'): '{path}'.")
        ficheros_normalizados.append({"path": path, "contenido": contenido})

    log_entry = datos.get("log_entry")
    if log_entry is not None and not isinstance(log_entry, str):
        raise IngestError("'log_entry' debe ser texto si está presente.")

    contradicciones = datos.get("contradicciones") or []
    preguntas = datos.get("preguntas_seguimiento") or []
    if not isinstance(contradicciones, list) or not isinstance(preguntas, list):
        raise IngestError("'contradicciones' y 'preguntas_seguimiento' deben ser listas.")

    return {
        "ficheros": ficheros_normalizados,
        "log_entry": (log_entry or "").strip(),
        "contradicciones": [str(c) for c in contradicciones],
        "preguntas_seguimiento": [str(p) for p in preguntas],
    }