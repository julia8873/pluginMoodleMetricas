"""
Extracción de texto de ficheros PDF para poder incorporarlos a la BdC.

Se mantiene como módulo aparte (en vez de meterlo en bot.py) para que la
lógica de "cómo se lee un PDF" esté aislada de la lógica de Matrix/GitHub,
y se pueda probar o cambiar de librería sin tocar el resto del bot.
"""

import io
import re

from pypdf import PdfReader

# Cualquier secuencia de 2+ letras (con acentos/ñ) cuenta como "palabra reconocible"
# a efectos de la heurística de calidad del texto extraído.
_PATRON_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}")


class PdfExtractionError(Exception):
    """Se lanza cuando un PDF no se puede leer (corrupto, cifrado, escaneado sin OCR, etc.)."""


# --------------------------------------------------------------------
# Heurística de calidad del texto extraído
# --------------------------------------------------------------------

def parece_texto_de_baja_calidad(texto: str) -> bool:
    """
    Detecta texto extraído de PDFs que en realidad es ruido de OCR de baja calidad
    o notación sin valor semántico (p.ej. símbolos de música, caracteres sueltos).

    Muchas apps de escaneo de móvil (CamScanner, Notes, Adobe Scan...) incrustan
    su propia capa de OCR dentro del PDF para hacerlo buscable. pypdf la lee como
    "texto seleccionable" aunque sea ilegible, o extrae símbolos sin sentido
    (notación musical, fragmentos de iconos).

    Esta función filtra esos casos comprobando la proporción de caracteres
    alfanuméricos, la densidad de palabras reales y la proporción de tokens
    de un solo carácter.
    """
    texto = texto.strip()
    if not texto:
        return True

    total_no_espacio = len(re.sub(r"\s+", "", texto))
    if total_no_espacio == 0:
        return True

    alfanumericos = len(re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]", texto))
    ratio_alfanumerico = alfanumericos / total_no_espacio

    tokens = texto.split()
    total_tokens = len(tokens)
    if total_tokens == 0:
        return True

    palabras_reconocibles = _PATRON_PALABRA.findall(texto)
    tokens_un_caracter = [t for t in tokens if len(t) == 1]

    ratio_palabras = len(palabras_reconocibles) / total_tokens
    ratio_un_caracter = len(tokens_un_caracter) / total_tokens

    # Umbrales:
    # 1. Mucho símbolo no alfanumérico.
    # 2. Muy pocas palabras reales (longitud >= 2).
    # 3. Demasiados tokens de un solo carácter: umbral bajo (0.25) porque incluso
    #    una proporción moderada de caracteres sueltos (notación musical, símbolos
    #    de partituras como w, b, &, #, œ, ˙) hace inútil el texto para el LLM.
    return (ratio_alfanumerico < 0.55 or 
            ratio_palabras < 0.45 or 
            ratio_un_caracter > 0.25)


# --------------------------------------------------------------------
# Extracción de texto seleccionable
# --------------------------------------------------------------------

def extraer_texto_pdf(contenido_binario: bytes, max_caracteres: int = 200_000) -> str:
    """
    Recibe los bytes crudos de un PDF y devuelve el texto concatenado de todas
    sus páginas. Solo debe usarse con PDFs que tengan texto seleccionable real;
    para PDFs escaneados usar transcribir_pdf_escaneado() en image_ocr.py.

    max_caracteres: corta el resultado para no disparar el tamaño del contexto
    que luego se manda al LLM (200k caracteres ~ 45-50k tokens, ya de sobra
    para un solo documento de estudio universitario).
    """
    try:
        lector = PdfReader(io.BytesIO(contenido_binario))
    except Exception as exc:
        raise PdfExtractionError(f"No se ha podido abrir el PDF: {exc}") from exc

    if lector.is_encrypted:
        # Algunos PDFs están "cifrados" solo con restricciones de permisos (sin
        # contraseña real): se intenta abrir con contraseña vacía antes de rendirse.
        try:
            lector.decrypt("")
        except Exception as exc:
            raise PdfExtractionError("El PDF está protegido con contraseña.") from exc

    partes = []
    for num_pagina, pagina in enumerate(lector.pages, start=1):
        try:
            texto_pagina = pagina.extract_text() or ""
        except Exception:
            texto_pagina = ""
        if texto_pagina.strip():
            partes.append(f"[Página {num_pagina}]\n{texto_pagina.strip()}")

    texto_completo = "\n\n".join(partes).strip()

    if not texto_completo:
        raise PdfExtractionError(
            "No se ha extraído texto del PDF (puede ser un PDF escaneado sin OCR)."
        )

    if len(texto_completo) > max_caracteres:
        texto_completo = texto_completo[:max_caracteres] + "\n\n[...documento truncado...]"

    return texto_completo