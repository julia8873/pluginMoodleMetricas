"""
Organización de la BdC en carpetas/asignaturas.

Este módulo NO habla con Matrix ni con GitHub directamente: solo contiene la
lógica de "qué carpeta le corresponde a un fichero" (saneado de nombres de
carpeta, interpretación de la respuesta del estudiante). bot.py es quien
conecta esto con los eventos de Matrix y con la API de GitHub, y quien
mantiene el estado de los lotes de subida en memoria.
"""

import re
from typing import List, Optional

# --------------------------------------------------------------------
# Constantes de tiempo
# --------------------------------------------------------------------

# Tiempo que se espera tras el último fichero recibido de un mismo estudiante
# en una misma sala antes de preguntar dónde guardarlos. Si llegan varios
# ficheros en menos de este tiempo (p.ej. selección múltiple en el cliente
# de Matrix, que Matrix entrega como eventos independientes), se agrupan en
# una sola pregunta en vez de preguntar fichero a fichero.
VENTANA_LOTE_SEGUNDOS = 6.0


# --------------------------------------------------------------------
# Saneado y resolución de rutas de carpeta
# --------------------------------------------------------------------

def sanitizar_carpeta(texto: str) -> str:
    """
    Convierte lo que ha escrito el estudiante en una ruta de carpeta válida
    para GitHub: sin '..' (path traversal), sin barras iniciales/finales, sin
    caracteres especiales problemáticos, espacios colapsados en guiones.
    Permite subcarpetas con '/' para representar asignatura/tema
    (p.ej. "Cálculo II / Tema 3" → "Calculo-II/Tema-3").
    """
    texto = texto.strip().strip("/")
    partes = [p.strip() for p in texto.split("/") if p.strip() and p.strip() not in ("..", ".")]
    partes_limpias = []
    for parte in partes:
        limpio = re.sub(r"\s+", "-", parte)
        limpio = re.sub(r"[^\w\-áéíóúüñÁÉÍÓÚÜÑ]", "", limpio)
        limpio = limpio.strip("-")
        if limpio:
            partes_limpias.append(limpio)
    return "/".join(partes_limpias)


def formatear_lista_carpetas(carpetas: List[str]) -> str:
    """Numera las carpetas existentes para que el estudiante pueda elegir con un número."""
    if not carpetas:
        return "(De momento no hay ninguna carpeta creada; escribe un nombre para crear una nueva.)"
    return "\n".join(f"{i}. {c}" for i, c in enumerate(carpetas, start=1))


def resolver_eleccion_carpeta(respuesta: str, carpetas: List[str]) -> Optional[str]:
    """
    Interpreta la respuesta del estudiante a "¿dónde lo guardo?":
    - "0", "raiz" o "raíz" → carpeta raíz (devuelve None; el caller usa raw_folder).
    - Un número → esa carpeta de la lista mostrada (ValueError si no existe).
    - Cualquier otro texto → nueva carpeta con ese nombre (sanitizado).
    """
    respuesta = respuesta.strip()
    if respuesta.lower() in ("0", "raiz", "raíz", "-"):
        return None
    if respuesta.isdigit():
        indice = int(respuesta)
        if 1 <= indice <= len(carpetas):
            return carpetas[indice - 1]
        raise ValueError(f"No hay ninguna carpeta con el número {indice}.")
    carpeta = sanitizar_carpeta(respuesta)
    return carpeta or None


# --------------------------------------------------------------------
# Interpretación de respuestas de lote
# --------------------------------------------------------------------

def es_respuesta_modo_lote(respuesta: str) -> Optional[bool]:
    """
    Interpreta la respuesta a "¿los guardo todos en el mismo sitio, o uno por uno?".
    Devuelve True para "todos juntos", False para "uno por uno", o None si no se
    reconoce la respuesta (para volver a preguntar sin perder el estado).
    """
    respuesta = respuesta.strip().lower()
    if respuesta in ("todos", "todo", "junto", "juntos", "mismo", "mismo sitio", "t"):
        return True
    if respuesta in ("uno por uno", "uno", "individual", "cada uno", "separado", "u"):
        return False
    return None