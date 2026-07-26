from .constants import PATRON_TEMA, PATRON_TIPO

def _extraer_modificadores(texto: str) -> tuple:
    """
    Busca 'tema:<...>' y 'tipo:<...>' en el argumento de un comando y los separa del
    resto del texto (nombre de concepto, enunciado, pregunta...).
    Devuelve (resto, tema, tipo_contenido).
    """
    tema = ""
    tipo_contenido = ""

    m = PATRON_TEMA.search(texto)
    if m:
        tema = m.group(1)
        texto = texto[: m.start()] + texto[m.end():]

    m = PATRON_TIPO.search(texto)
    if m:
        tipo_contenido = m.group(1).lower()
        texto = texto[: m.start()] + texto[m.end():]

    return texto.strip(), tema, tipo_contenido
