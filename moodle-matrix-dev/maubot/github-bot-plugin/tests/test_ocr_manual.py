"""
Smoke-test manual del pipeline de OCR para apuntes manuscritos.

NO es un test unitario clásico: requiere un backend LLM real configurado
(las credenciales se leen de las variables de entorno LLM_BASE_URL, LLM_API_KEY
y LLM_VISION_MODEL). Sirve para verificar que image_ocr.py funciona correctamente
con un modelo de visión concreto antes de desplegar el bot.

Uso:
    set LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
    set LLM_API_KEY=tu-api-key
    set LLM_VISION_MODEL=gemini-2.0-flash
    python tests/test_ocr_manual.py ruta/a/apuntes.jpg

Si no se pasa ningún fichero, se usa la imagen de prueba tests/sample_apuntes.jpg
(si existe) o se aborta con un mensaje de error claro.
"""

import asyncio
import os
import sys
from pathlib import Path

# Añadir el directorio raíz del proyecto al path para poder importar github_bot.
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from github_bot.image_ocr import OcrError, es_imagen_de_apuntes, transcribir_imagen, transcribir_pdf_escaneado
from github_bot.llm_provider import LLMProvider


def _crear_llm_vision() -> LLMProvider:
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    api_key  = os.environ.get("LLM_API_KEY", "").strip()
    model    = os.environ.get("LLM_VISION_MODEL", "").strip()
    if not base_url or not api_key or not model:
        print(
            "ERROR: Debes definir las variables de entorno LLM_BASE_URL, "
            "LLM_API_KEY y LLM_VISION_MODEL antes de ejecutar este test.\n"
            "Ejemplo (PowerShell):\n"
            "  $env:LLM_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai'\n"
            "  $env:LLM_API_KEY  = 'tu-api-key'\n"
            "  $env:LLM_VISION_MODEL = 'gemini-2.0-flash'"
        )
        sys.exit(1)
    return LLMProvider(base_url, api_key, model)


async def test_imagen(ruta: Path, llm: LLMProvider) -> None:
    print(f"\n--- Transcribiendo imagen: {ruta.name} ---")
    contenido = ruta.read_bytes()
    extension = ruta.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp",
        ".heic": "image/heic", ".heif": "image/heif",
    }
    mime = mime_map.get(extension, "image/jpeg")

    try:
        texto = await transcribir_imagen(contenido, mime, llm)
    except OcrError as exc:
        print(f"FALLO: {exc}")
        return

    print(f"OK — {len(texto)} caracteres transcritos.\n")
    print("--- Primeros 500 caracteres ---")
    print(texto[:500])

    # Verificación básica: el resultado debe contener al menos algo legible.
    if len(texto.strip()) < 20:
        print("\nADVERTENCIA: la transcripción parece demasiado corta. "
              "Revisa que el modelo de visión sea el correcto.")
    else:
        print("\n✓ Transcripción supera el mínimo de 20 caracteres.")

    # Si hay LaTeX, es una buena señal para apuntes matemáticos.
    if "$" in texto:
        print("✓ Se detectó notación LaTeX en la transcripción.")
    else:
        print("(No se detectó LaTeX; puede ser normal si la imagen no tiene fórmulas.)")


async def test_pdf(ruta: Path, llm: LLMProvider) -> None:
    print(f"\n--- Transcribiendo PDF escaneado: {ruta.name} ---")
    contenido = ruta.read_bytes()

    try:
        texto, paginas_fallidas = await transcribir_pdf_escaneado(contenido, llm, max_paginas=3)
    except OcrError as exc:
        print(f"FALLO: {exc}")
        return

    print(f"OK — {len(texto)} caracteres transcritos.")
    if paginas_fallidas:
        print(f"Páginas con error: {paginas_fallidas}")
    print("\n--- Primeros 500 caracteres ---")
    print(texto[:500])

    if len(texto.strip()) < 20:
        print("\nADVERTENCIA: transcripción demasiado corta.")
    else:
        print("\n✓ Transcripción supera el mínimo de 20 caracteres.")


async def main() -> None:
    llm = _crear_llm_vision()

    if len(sys.argv) > 1:
        ruta = Path(sys.argv[1])
    else:
        # Buscar imagen de muestra por defecto.
        candidatos = [
            Path(__file__).parent / "sample_apuntes.jpg",
            Path(__file__).parent / "sample_apuntes.png",
        ]
        ruta = next((p for p in candidatos if p.exists()), None)
        if ruta is None:
            print(
                "ERROR: No se ha pasado ningún fichero y no existe tests/sample_apuntes.jpg.\n"
                "Uso: python tests/test_ocr_manual.py ruta/a/apuntes.jpg"
            )
            sys.exit(1)

    if not ruta.exists():
        print(f"ERROR: No existe el fichero '{ruta}'.")
        sys.exit(1)

    if ruta.suffix.lower() == ".pdf":
        await test_pdf(ruta, llm)
    elif es_imagen_de_apuntes(ruta.name):
        await test_imagen(ruta, llm)
    else:
        print(f"ERROR: Extensión no reconocida: {ruta.suffix}. "
              "Usa .jpg, .jpeg, .png, .webp, .heic, .heif o .pdf")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
