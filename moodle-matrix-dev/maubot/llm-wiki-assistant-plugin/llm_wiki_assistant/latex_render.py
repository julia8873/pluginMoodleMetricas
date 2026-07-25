# --8<-- [start:file_desc]
"""
Renderizado de fórmulas LaTeX como imágenes PNG para enviar en Matrix.

Element y la mayoría de clientes de Matrix no renderizan LaTeX de forma nativa:
si el LLM devuelve $\\int_0^1 f(x)\\,dx$, el estudiante ve el código fuente.
Este módulo detecta los bloques LaTeX en el texto de respuesta y los renderiza
a imágenes PNG con matplotlib.mathtext (no requiere instalación de LaTeX en el
servidor, solo la librería Python matplotlib).

Se mantiene como módulo aparte, igual que image_ocr.py y pdf_ingest.py, para
poder cambiar el motor de renderizado sin tocar el resto del bot.

Limitación conocida: matplotlib.mathtext no soporta todos los entornos LaTeX
(p.ej. \\begin{align}, \\begin{matrix}, \\cases...). Cuando el renderizado
falla para una fórmula concreta, esa fórmula queda en texto plano en el mensaje
(el body de texto plano siempre conserva el LaTeX original como fallback).
"""

import io
import re
from typing import Callable, Optional

# --------------------------------------------------------------------
# Expresiones regulares para detectar LaTeX
# --------------------------------------------------------------------

# El orden de procesado es importante: primero $$...$$ para no partir los bloques
# display en dos inline. Los patrones son no avaros (?.+?) para no tragarse varios
# bloques a la vez. El lookbehind/lookahead evita que $$ sea tratado como dos $.
_PATRON_DISPLAY = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_PATRON_INLINE  = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", re.DOTALL)


def tiene_latex(texto: str) -> bool:
    """Devuelve True si el texto contiene al menos una expresión LaTeX ($...$ o $$...$$)."""
    return bool(_PATRON_DISPLAY.search(texto) or _PATRON_INLINE.search(texto))


# --------------------------------------------------------------------
# Renderizado de fórmulas individuales
# --------------------------------------------------------------------

def renderizar_formula(formula: str, display: bool = False) -> Optional[bytes]:
    """
    Renderiza una fórmula LaTeX a PNG con matplotlib.mathtext.

    Devuelve los bytes del PNG, o None si el renderizado falla. El caller puede
    entonces dejar esa fórmula en texto plano sin romper el resto del mensaje.

    display=True: modo "display" (mayor, para bloques $$...$$).
    display=False: modo "inline" (tamaño normal, para $...$).
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # Backend sin ventana, seguro en entornos de servidor.
        import matplotlib.pyplot as plt
    except ImportError:
        return None  # matplotlib no instalado: fallback a texto plano.

    formula_latex = formula.strip()
    if not formula_latex:
        return None

    fontsize = 14 if display else 12
    formula_con_delimitador = f"${formula_latex}$"

    try:
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0)
        fig.text(0, 0, formula_con_delimitador, fontsize=fontsize, color="black")
        buf = io.BytesIO()
        fig.savefig(
            buf, format="png", bbox_inches="tight", pad_inches=0.1,
            facecolor="none", transparent=True, dpi=150,
        )
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        try:
            plt.close("all")
        except Exception:
            pass
        return None


# --------------------------------------------------------------------
# Procesado del texto completo con sustitución de fórmulas
# --------------------------------------------------------------------

async def procesar_texto_con_latex(
    texto: str,
    upload_fn: Callable,  # async (bytes, str) -> Optional[str]: sube PNG, devuelve mxc://
) -> tuple:
    """
    Detecta y renderiza todos los bloques LaTeX del texto para enviarlos en un
    mensaje HTML de Matrix.

    Estrategia de sustitución por placeholders:
    1. Se reemplazan todos los bloques LaTeX ($$...$$ e $...$) por marcadores
       internos únicos, para que el escapado HTML no confunda los $ con HTML.
    2. Se escapa el texto restante a HTML.
    3. Se renderizan las fórmulas y se suben como imágenes; si una falla, se
       deja el LaTeX original (escapado) en su lugar.

    Devuelve (body_plano, formatted_body_html):
    - body_plano: el texto original con LaTeX tal cual (fallback para clientes sin HTML).
    - formatted_body_html: texto con cada fórmula sustituida por <img mxc://...>.

    upload_fn: callable async que recibe (bytes_png, alt_text) y devuelve el URI
    mxc:// de la imagen subida, o None si la subida falla.
    """
    body_plano = texto

    # Paso 1: marcar los bloques LaTeX con placeholders únicos.
    display_bloques: dict = {}
    inline_bloques: dict = {}
    contador = [0]

    def _marcar_display(m: re.Match) -> str:
        k = f"\x00DISP{contador[0]}\x00"
        display_bloques[k] = m.group(1)
        contador[0] += 1
        return k

    def _marcar_inline(m: re.Match) -> str:
        k = f"\x00INLN{contador[0]}\x00"
        inline_bloques[k] = m.group(1)
        contador[0] += 1
        return k

    # Primero display, luego inline, para no partir $$ en dos $.
    texto_con_markers = _PATRON_DISPLAY.sub(_marcar_display, texto)
    texto_con_markers = _PATRON_INLINE.sub(_marcar_inline, texto_con_markers)

    # Paso 2: escapar HTML del texto residual (sin fórmulas).
    html_base = _escapar_html(texto_con_markers)

    # Paso 3: sustituir cada placeholder por <img> o por LaTeX en texto plano.
    for placeholder, formula in display_bloques.items():
        png = renderizar_formula(formula, display=True)
        if png is not None:
            mxc = await upload_fn(png, formula[:100])
            if mxc is not None:
                reemplazo = (
                    f'<img src="{mxc}" alt="{_escapar_attr(f"$${formula}$$")}" '
                    f'title="{_escapar_attr(formula)}">'
                )
                html_base = html_base.replace(placeholder, reemplazo)
                continue
        # Renderizado o subida fallida: dejar el LaTeX escapado en texto plano.
        html_base = html_base.replace(placeholder, _escapar_html(f"$${formula}$$"))

    for placeholder, formula in inline_bloques.items():
        png = renderizar_formula(formula, display=False)
        if png is not None:
            mxc = await upload_fn(png, formula[:100])
            if mxc is not None:
                reemplazo = (
                    f'<img src="{mxc}" alt="{_escapar_attr(f"${formula}$")}" '
                    f'title="{_escapar_attr(formula)}">'
                )
                html_base = html_base.replace(placeholder, reemplazo)
                continue
        html_base = html_base.replace(placeholder, _escapar_html(f"${formula}$"))

    return body_plano, html_base


# --------------------------------------------------------------------
# Utilidades de escapado HTML
# --------------------------------------------------------------------

def _escapar_html(texto: str) -> str:
    """Escapa los cuatro caracteres especiales de HTML en texto plano."""
    return (
        texto
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _escapar_attr(texto: str) -> str:
    """Escapa texto para usarlo dentro de un atributo HTML (alt, title)."""
    return texto.replace("&", "&amp;").replace('"', "&quot;").replace("'", "&#39;")

# --8<-- [end:file_desc]
