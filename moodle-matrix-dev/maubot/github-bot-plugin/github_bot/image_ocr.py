"""
Transcripción de apuntes escritos a mano (fotos, o PDFs que son en realidad
un escaneo de páginas) para poder incorporarlos a la BdC.

pypdf (pdf_ingest.py) solo sabe leer texto ya seleccionable. Aquí se usa en
su lugar el mismo LLM configurado para !pregunta (admite imágenes además de
texto), que es mucho más fiable que un OCR clásico para letra manuscrita.

Se mantiene como módulo aparte por lo mismo que pdf_ingest.py: para poder
cambiar de motor (por ejemplo a un OCR dedicado) sin tocar el resto del bot.
"""

import base64
from typing import Optional

import fitz  # PyMuPDF: renderiza páginas de PDF como imágenes sin depender de binarios externos

from .llm_provider import LLMProvider

# --------------------------------------------------------------------
# Constantes de configuración
# --------------------------------------------------------------------

# Resolución de renderizado de páginas escaneadas. 3.0 ~ 216 dpi: para letra
# manuscrita con notación matemática densa (fracciones apiladas, subíndices,
# símbolos como ∃/∀/δ) 2.0 (~144 dpi) se queda corto y aumenta el riesgo de que
# el modelo "adivine" en vez de leer el trazo real. El coste son imágenes más
# pesadas (más tokens de entrada), pero para este caso de uso compensa.
ZOOM_RENDERIZADO_PDF = 3.0

# Extensiones que se aceptan como "foto de apuntes". Se incluyen .heif y .heic
# porque distintas versiones de iOS generan ambas variantes del mismo formato.
# es_imagen_de_apuntes() usa .lower(), así que .JPG y similares también son válidas.
EXTENSIONES_IMAGEN_VALIDAS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")


# --------------------------------------------------------------------
# Excepciones y helpers públicos
# --------------------------------------------------------------------

class OcrError(Exception):
    """Se lanza cuando no se ha podido transcribir una imagen o un PDF escaneado."""


def es_imagen_de_apuntes(nombre_archivo: str) -> bool:
    """Devuelve True si la extensión del fichero corresponde a una imagen de apuntes."""
    return nombre_archivo.lower().endswith(EXTENSIONES_IMAGEN_VALIDAS)


# --------------------------------------------------------------------
# Transcripción de imágenes individuales
# --------------------------------------------------------------------

async def transcribir_imagen(
    contenido_binario: bytes, mime_type: str, llm: LLMProvider
) -> str:
    """
    Manda una única imagen al LLM multimodal y devuelve la transcripción en
    Markdown (fórmulas en LaTeX, estructura conservada con sintaxis Markdown).
    Lanza OcrError si el modelo no responde o devuelve texto vacío.
    """
    b64 = base64.b64encode(contenido_binario).decode("ascii")
    try:
        texto = await llm.transcribir_imagen(b64, mime_type)
    except Exception as exc:
        raise OcrError(f"Error al consultar el modelo de visión: {exc}") from exc

    texto = (texto or "").strip()
    if not texto:
        raise OcrError("El modelo no ha devuelto ninguna transcripción para la imagen.")
    return texto


# --------------------------------------------------------------------
# Transcripción de PDFs escaneados (página a página)
# --------------------------------------------------------------------

async def transcribir_pdf_escaneado(
    contenido_binario: bytes, llm: LLMProvider, max_paginas: int = 30, progress_callback = None
) -> tuple:
    """
    Para PDFs sin texto seleccionable (escaneo o fotos de apuntes pegadas):
    renderiza cada página como imagen y la transcribe con el LLM, página a página.

    max_paginas: límite de seguridad para no disparar el número de llamadas al LLM
    (y el tiempo de espera del estudiante) si se sube un PDF enorme.

    progress_callback: función asíncrona opcional que recibe (pagina_actual, total_paginas)
    para informar de avances en el chat durante PDFs largos.

    Devuelve (texto_completo, paginas_fallidas), donde paginas_fallidas es una lista
    de (numero_pagina, mensaje_error) para cada página que no se pudo transcribir.
    """
    try:
        documento = fitz.open(stream=contenido_binario, filetype="pdf")
    except Exception as exc:
        raise OcrError(f"No se ha podido abrir el PDF para renderizarlo: {exc}") from exc

    total_paginas = documento.page_count
    if total_paginas == 0:
        raise OcrError("El PDF no tiene páginas.")

    num_paginas = min(total_paginas, max_paginas)
    matriz = fitz.Matrix(ZOOM_RENDERIZADO_PDF, ZOOM_RENDERIZADO_PDF)

    partes: list = []
    paginas_fallidas: list = []
    for i in range(num_paginas):
        if progress_callback and (i > 0 and i % 3 == 0):
            try:
                await progress_callback(i + 1, num_paginas)
            except Exception:
                pass

        pagina = documento.load_page(i)
        pixmap = pagina.get_pixmap(matrix=matriz)
        imagen_png = pixmap.tobytes("png")

        try:
            texto_pagina = await transcribir_imagen(imagen_png, "image/png", llm)
        except OcrError as exc:
            msg_err = str(exc).lower()
            # Si el error en cualquier página es fatal (autenticación, cuota, timeout, API key no configurada,
            # o error 401/403/404/429), abortamos INMEDIATAMENTE en vez de esperar en silencio a que fallen
            # todas las demás páginas del PDF.
            errores_fatales = ("401", "403", "404", "429", "timeout", "api_key", "clave api", "cuota", "bearer")
            if any(e in msg_err for e in errores_fatales) or (len(paginas_fallidas) >= 1 and paginas_fallidas[-1][1] == str(exc)):
                documento.close()
                raise OcrError(
                    f"Error fatal o recurrente al consultar el modelo de visión en la página {i + 1}/{num_paginas}: {exc}"
                )

            texto_pagina = f"[No se ha podido transcribir esta página: {exc}]"
            paginas_fallidas.append((i + 1, str(exc)))

        partes.append(f"[Página {i + 1}]\n{texto_pagina}")

    documento.close()

    if paginas_fallidas and len(paginas_fallidas) == num_paginas:
        raise OcrError(
            f"No se ha podido transcribir ninguna de las {num_paginas} páginas. "
            f"Error en la primera página: {paginas_fallidas[0][1]}"
        )

    if total_paginas > max_paginas:
        partes.append(
            f"\n[...documento truncado: solo se han transcrito las primeras "
            f"{max_paginas} de {total_paginas} páginas...]"
        )

    texto_completo = "\n\n".join(partes).strip()
    if not texto_completo:
        raise OcrError("No se ha podido transcribir ninguna página del PDF.")

    return texto_completo, paginas_fallidas