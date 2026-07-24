# --8<-- [start:file_desc]
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
# --8<-- [end:file_desc]


class EstudioError(Exception):
    """Se lanza cuando el LLM no devuelve la respuesta con el formato esperado."""


# --------------------------------------------------------------------
# Filtro por tipo de contenido (modificador `tipo:`)
# --------------------------------------------------------------------

# Permite pedir específicamente una definición, un teorema, una fórmula o un
# ejemplo, en vez de dejar que el LLM elija libremente. Las claves son lo que
# el estudiante escribe tras `tipo:`; los valores son la frase inyectada en el prompt.
TIPOS_CONTENIDO = {
    "definicion": "una DEFINICIÓN formal de un concepto (no un teorema ni una fórmula)",
    "definición": "una DEFINICIÓN formal de un concepto (no un teorema ni una fórmula)",
    "teorema": "un TEOREMA o PROPOSICIÓN (su enunciado; puede incluir sus hipótesis)",
    "proposicion": "un TEOREMA o PROPOSICIÓN (su enunciado; puede incluir sus hipótesis)",
    "proposición": "un TEOREMA o PROPOSICIÓN (su enunciado; puede incluir sus hipótesis)",
    "formula": "una FÓRMULA o propiedad matemática/técnica concreta",
    "fórmula": "una FÓRMULA o propiedad matemática/técnica concreta",
    "ejemplo": "un EJEMPLO concreto de aplicación de algún concepto",
}

# "todo"/"todos" es un valor válido de `tipo:` (para poder pedir explícitamente
# "todos los tipos" en !repasartema) pero no filtra nada: se trata igual que si
# no se hubiera indicado tipo.
_TIPOS_SIN_FILTRO = {"", "todo", "todos"}


def _instruccion_tipo(tipo: str) -> str:
    """Devuelve la frase a añadir al prompt para un `tipo:` dado, o '' si es vacío/no reconocido."""
    tipo_normalizado = (tipo or "").strip().lower()
    if tipo_normalizado in _TIPOS_SIN_FILTRO:
        return ""
    descripcion = TIPOS_CONTENIDO.get(tipo_normalizado)
    if not descripcion:
        return ""
    return f" Tiene que tratarse específicamente de {descripcion}."


# --------------------------------------------------------------------
# Generación de preguntas
# --------------------------------------------------------------------

async def elegir_concepto(contexto: str, llm: LLMProvider, tipo: str = "") -> str:
    """Le pide al LLM un concepto concreto de la BdC, para !concepto y !feynman sin argumento."""
    instruccion = (
        "Elige UN concepto clave y concreto del contenido de la BdC, uno que tenga sentido "
        "pedirle a un estudiante que defina o explique (no un tema demasiado amplio)."
        f"{_instruccion_tipo(tipo)} "
        "Responde ÚNICAMENTE con el nombre del concepto, sin comillas ni explicación."
    )
    concepto = await llm.generar_texto(instruccion, contexto)
    return concepto.strip().strip('"').strip("'")


# Umbral de caracteres a partir del cual un archivo se subdivide por cabeceras
# markdown en vez de mandarse entero en una sola llamada al LLM. Con contenidos
# largos, pedirle al modelo "TODOS los conceptos" de un tirón hace que en la
# práctica solo cubra bien el principio del texto (el típico problema de
# "lost in the middle" de los LLM con contextos largos): por eso se trocea.
UMBRAL_SUBDIVISION_ARCHIVO = 6000

# Tope al número de secciones (= llamadas al LLM) que genera _dividir_en_secciones
# para una sola sesión de !repasartema. Trocear ayuda a cubrir todo el tema, pero
# cada sección es una llamada al LLM: sin límite, un tema muy amplio podría consumir
# buena parte de la cuota diaria del modelo de golpe.
MAX_SECCIONES_LISTAR_CONCEPTOS = 8

# Tope a cuántas de esas llamadas se lanzan a la vez. Además del límite diario,
# muchos proveedores también limitan las peticiones por minuto/ráfaga: lanzar las 8
# secciones en paralelo de golpe puede disparar ese límite aunque quede cuota.
MAX_LLAMADAS_SIMULTANEAS = 3


def _dividir_por_archivo(contexto: str) -> list:
    """Divide el contenido de la BdC en un bloque por archivo, usando la cabecera
    '## Archivo: ...' que añade _recorrer_carpeta en bot.py."""
    partes = re.split(r"(?=^## Archivo: )", contexto, flags=re.MULTILINE)
    return [p.strip() for p in partes if p.strip()]


def _subdividir_si_largo(seccion: str) -> list:
    """Si un archivo es muy largo, lo subdivide por sus cabeceras markdown (#, ##, ###),
    agrupando cabeceras consecutivas en bloques de hasta UMBRAL_SUBDIVISION_ARCHIVO
    caracteres. Conserva la línea '## Archivo: ...' como contexto en cada sub-bloque."""
    if len(seccion) <= UMBRAL_SUBDIVISION_ARCHIVO:
        return [seccion]

    lineas = seccion.splitlines()
    if lineas and lineas[0].startswith("## Archivo:"):
        cabecera, cuerpo = lineas[0], "\n".join(lineas[1:])
    else:
        cabecera, cuerpo = "", seccion

    trozos = re.split(r"(?=^#{1,3}\s)", cuerpo, flags=re.MULTILINE)
    trozos = [t.strip() for t in trozos if t.strip()]
    if len(trozos) <= 1:
        return [seccion]

    bloques, actual = [], ""
    for trozo in trozos:
        if actual and len(actual) + len(trozo) > UMBRAL_SUBDIVISION_ARCHIVO:
            bloques.append(actual)
            actual = trozo
        else:
            actual = f"{actual}\n\n{trozo}" if actual else trozo
    if actual:
        bloques.append(actual)

    return [f"{cabecera}\n{b}" if cabecera else b for b in bloques]


def _dividir_en_secciones(contexto: str) -> list:
    """Trocea el contenido de la BdC en secciones manejables (por archivo, y dentro de
    archivos largos por cabecera) para pedirle al LLM los conceptos de cada una por
    separado. El resultado se acota a MAX_SECCIONES_LISTAR_CONCEPTOS."""
    secciones = []
    for archivo in _dividir_por_archivo(contexto):
        secciones.extend(_subdividir_si_largo(archivo))
    secciones = secciones or [contexto]
    return _limitar_num_secciones(secciones, MAX_SECCIONES_LISTAR_CONCEPTOS)


def _limitar_num_secciones(secciones: list, maximo: int) -> list:
    """Si hay más secciones que `maximo`, fusiona secciones contiguas en grupos
    aproximadamente iguales (en vez de descartar secciones, que dejaría partes del
    tema sin repasar)."""
    if len(secciones) <= maximo:
        return secciones
    tamano_grupo = math.ceil(len(secciones) / maximo)
    return [
        "\n\n".join(secciones[i:i + tamano_grupo])
        for i in range(0, len(secciones), tamano_grupo)
    ]


def _entrelazar_y_deduplicar(listas_por_seccion: list) -> list:
    """Combina las listas de conceptos de cada sección ALTERNANDO entre ellas (1.º de
    cada sección, luego el 2.º de cada una, etc.) en vez de concatenarlas en orden.
    Así, si luego se trunca el número de conceptos, el resultado reparte preguntas
    por todo el temario en vez de agotarse en las primeras secciones."""
    vistos = set()
    combinados = []
    max_len = max((len(lista) for lista in listas_por_seccion), default=0)
    for i in range(max_len):
        for lista in listas_por_seccion:
            if i >= len(lista):
                continue
            concepto = lista[i]
            clave = concepto.lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            combinados.append(concepto)
    return combinados


async def listar_conceptos(contexto: str, llm: LLMProvider, tipo: str = "") -> list:
    """
    Le pide al LLM TODOS los conceptos (de un tipo dado, o de cualquier tipo) que
    aparecen en el contenido. Usado por !repasartema para plantear una sesión de
    repaso que recorra un tema entero en vez de un concepto suelto.

    El contenido se trocea en secciones y se pide la lista de conceptos de cada una
    por separado, con un límite de llamadas simultáneas (MAX_LLAMADAS_SIMULTANEAS).
    Si TODAS las secciones fallan, se lanza EstudioError con el motivo de la primera.
    """
    instruccion = (
        "Extrae del contenido de la BdC los conceptos clave que aparecen en ESTE fragmento, "
        "uno por línea, sin numerar, sin viñetas y sin explicación adicional. Prioriza "
        "DEFINICIONES formales, TEOREMAS o PROPOSICIONES (su enunciado) y FÓRMULAS o "
        "propiedades importantes, sobre todo las que se necesiten para resolver ejercicios "
        "o demostrar otros resultados; no te limites a nombrar de pasada anécdotas, "
        "comentarios introductorios o motivación sin contenido técnico."
        f"{_instruccion_tipo(tipo)} "
        "No inventes conceptos que no estén en el contenido, e incluye todos los relevantes "
        "que encuentres en este fragmento, aunque sean muchos. "
        "Responde ÚNICAMENTE con la lista, un concepto por línea."
    )

    secciones = _dividir_en_secciones(contexto)
    semaforo = asyncio.Semaphore(MAX_LLAMADAS_SIMULTANEAS)

    async def _procesar_seccion(seccion: str):
        """Devuelve (lista_conceptos, None) si ha ido bien, o (None, excepcion) si ha fallado."""
        async with semaforo:
            try:
                bruto = await llm.generar_texto(instruccion, seccion)
            except Exception as exc:
                return None, exc
        return _parsear_lista_conceptos(bruto), None

    resultados = await asyncio.gather(*(_procesar_seccion(s) for s in secciones))
    listas_ok = [lista for lista, error in resultados if error is None]
    errores = [error for _, error in resultados if error is not None]

    if not listas_ok and errores:
        # Ninguna sección procesada: se propaga el motivo del primer error para que
        # el estudiante vea un mensaje claro en vez de "No he encontrado conceptos".
        raise EstudioError(str(errores[0]))

    return _entrelazar_y_deduplicar(listas_ok)


def _parsear_lista_conceptos(bruto: str) -> list:
    """Convierte la lista devuelta por el LLM (una línea por concepto) en una lista de
    strings limpia, sin numeración/viñetas ni duplicados (comparados en minúsculas)."""
    conceptos = []
    vistos = set()
    for linea in bruto.splitlines():
        limpio = re.sub(r"^[\s\-\*•\d\.\)]+", "", linea).strip().strip('"').strip("'")
        if not limpio:
            continue
        clave = limpio.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        conceptos.append(limpio)
    return conceptos


async def generar_preguntas_para_conceptos(conceptos: list, contexto: str, llm: LLMProvider, tipo: str = "") -> list:
    """
    Genera, en UNA sola llamada al LLM, una pregunta de repaso para CADA concepto
    de la lista (en el mismo orden). Devuelve una lista de {"concepto": ..., "pregunta": ...};
    si el modelo desordena algún concepto, simplemente sale con menos elementos.
    """
    lista_conceptos = "\n".join(f"- {c}" for c in conceptos)
    instruccion = (
        "Genera UNA pregunta de repaso para CADA UNO de los siguientes conceptos de la BdC, "
        "en el mismo orden en que se dan (no te dejes ninguno sin pregunta, y no añadas "
        f"conceptos nuevos que no estén en la lista).{_instruccion_tipo(tipo)}\n\n"
        f"CONCEPTOS:\n{lista_conceptos}\n\n"
        "Responde con un bloque por concepto, EXACTAMENTE en este formato, separando cada "
        "bloque del siguiente con una línea que contenga solo tres guiones (---), sin nada "
        "más antes, entre o después de los bloques:\n"
        "CONCEPTO: <nombre, igual al de la lista>\nPREGUNTA: <la pregunta>"
    )
    bruto = await llm.generar_texto(instruccion, contexto)
    preguntas = _parsear_lote_preguntas(bruto)
    if not preguntas:
        raise EstudioError("el modelo no ha devuelto ninguna pregunta en el formato esperado.")
    return preguntas


def _parsear_lote_preguntas(bruto: str) -> list:
    """Divide la respuesta en bloques por '---' y parsea cada uno con _parsear_concepto_pregunta.
    Los bloques mal formados se descartan en silencio (no abortan toda la sesión)."""
    preguntas = []
    for bloque in re.split(r"\n\s*-{3,}\s*\n", bruto):
        try:
            preguntas.append(_parsear_concepto_pregunta(bloque))
        except EstudioError:
            continue
    return preguntas


async def generar_flashcard(contexto: str, llm: LLMProvider, tipo: str = "") -> dict:
    """Genera una flashcard de repaso: {"concepto": ..., "pregunta": ...}."""
    instruccion = (
        "Genera UNA pregunta de repaso tipo flashcard sobre un concepto concreto del contenido "
        "de la BdC (distinta cada vez que se te pida). Puede ser sobre una definición, una "
        f"propiedad, una fórmula o una relación entre conceptos.{_instruccion_tipo(tipo)}\n"
        "Responde EXACTAMENTE en este formato, sin nada más:\n"
        "CONCEPTO: <nombre corto del concepto>\n"
        "PREGUNTA: <la pregunta>"
    )
    bruto = await llm.generar_texto(instruccion, contexto)
    return _parsear_concepto_pregunta(bruto)


async def generar_ejercicio(contexto: str, llm: LLMProvider, tipo: str = "") -> dict:
    """Propone un ejercicio más aplicado que una flashcard (no solo memorístico)."""
    instruccion = (
        "Propón UN ejercicio o problema práctico (distinto cada vez) basado en el contenido de "
        "la BdC, del estilo de los que se piden en clase (aplicar una fórmula, resolver un caso "
        f"concreto, demostrar una propiedad corta, etc.).{_instruccion_tipo(tipo)}\n"
        "Responde EXACTAMENTE en este formato, sin nada más:\n"
        "CONCEPTO: <tema principal del ejercicio>\n"
        "PREGUNTA: <el enunciado del ejercicio>"
    )
    bruto = await llm.generar_texto(instruccion, contexto)
    return _parsear_concepto_pregunta(bruto)


def _parsear_concepto_pregunta(bruto: str) -> dict:
    concepto_m = re.search(r"CONCEPTO:\s*(.+)", bruto)
    pregunta_m = re.search(r"PREGUNTA:\s*(.+)", bruto, re.DOTALL)
    if not concepto_m or not pregunta_m:
        raise EstudioError("el modelo no ha devuelto la pregunta en el formato esperado.")
    return {
        "concepto": concepto_m.group(1).strip(),
        "pregunta": pregunta_m.group(1).strip(),
    }


# --------------------------------------------------------------------
# Búsqueda de ejercicios por técnica o teorema (!ejerciciostema)
# --------------------------------------------------------------------

async def buscar_ejercicios_por_tecnica(tecnica: str, contexto: str, llm: LLMProvider) -> list:
    """
    Busca en el contenido de la BdC los ejercicios o problemas que se pueden resolver
    usando o aplicando la técnica, teorema o herramienta indicada. Devuelve una lista
    de dicts con enunciado, fichero, cómo aplica la técnica, y solución (si está en
    el mismo fichero).

    Si el LLM no encuentra ningún ejercicio aplicable, devuelve lista vacía.
    Si el LLM falla, propaga la excepción para que el handler la muestre al estudiante.
    """
    instruccion = (
        f"Eres un asistente de estudio universitario. A continuación tienes el contenido de "
        f"la BdC (apuntes y ejercicios del estudiante). Tu tarea es identificar qué ejercicios "
        f"o problemas concretos se pueden resolver usando o aplicando: \"{tecnica}\".\n\n"
        "Para cada ejercicio que identifiques, devuelve un bloque con EXACTAMENTE este formato "
        "(separa bloques con una línea que contenga solo tres guiones **---**):\n"
        "ENUNCIADO: <el enunciado completo, tal como aparece en los apuntes>\n"
        "FICHERO: <ruta del fichero de la BdC donde aparece>\n"
        "TECNICA: <explicación breve de cómo aplica la técnica a este ejercicio>\n"
        "SOLUCION: <la solución si aparece en el mismo fichero, o 'No disponible'>\n\n"
        "Si no encuentras ningún ejercicio aplicable, responde únicamente: NINGUNO\n"
        "IMPORTANTE: solo incluye ejercicios que aparezcan LITERALMENTE en el contenido "
        "de la BdC; no inventes enunciados."
    )
    bruto = await llm.generar_texto(instruccion, contexto)
    bruto = bruto.strip()

    primera_linea = bruto.upper().splitlines()[0] if bruto else ""
    if "NINGUNO" in primera_linea:
        return []
    return _parsear_lote_ejerciciostema(bruto)


def _parsear_lote_ejerciciostema(bruto: str) -> list:
    """
    Parsea la respuesta del LLM para !ejerciciostema: divide por '---' y extrae
    ENUNCIADO, FICHERO, TECNICA y SOLUCION de cada bloque, con tolerancia a bloques
    mal formados (los descarta en silencio en vez de abortar toda la respuesta).
    """
    ejercicios = []
    for bloque in re.split(r"\n\s*-{3,}\s*\n", bruto):
        bloque = bloque.strip()
        if not bloque:
            continue

        enunciado_m = re.search(
            r"ENUNCIADO:\s*(.+?)(?=\nFICHERO:|\nTECNICA:|\nSOLUCION:|$)", bloque, re.DOTALL | re.IGNORECASE
        )
        fichero_m = re.search(
            r"FICHERO:\s*(.+?)(?=\nENUNCIADO:|\nTECNICA:|\nSOLUCION:|$)", bloque, re.DOTALL | re.IGNORECASE
        )
        tecnica_m = re.search(
            r"TECNICA:\s*(.+?)(?=\nENUNCIADO:|\nFICHERO:|\nSOLUCION:|$)", bloque, re.DOTALL | re.IGNORECASE
        )
        solucion_m = re.search(
            r"SOLUCION:\s*(.+?)(?=\nENUNCIADO:|\nFICHERO:|\nTECNICA:|$)", bloque, re.DOTALL | re.IGNORECASE
        )

        if not enunciado_m:
            continue  # Bloque sin enunciado: se descarta silenciosamente.

        solucion = solucion_m.group(1).strip() if solucion_m else ""
        if solucion.lower() in ("no disponible", "no disponible.", "ninguna", "n/a", ""):
            solucion = ""

        ejercicios.append({
            "enunciado": enunciado_m.group(1).strip(),
            "fichero": fichero_m.group(1).strip() if fichero_m else "desconocido",
            "tecnica": tecnica_m.group(1).strip() if tecnica_m else "",
            "solucion": solucion,
        })
    return ejercicios


# --------------------------------------------------------------------
# Evaluación de la respuesta del estudiante
# --------------------------------------------------------------------

async def evaluar_respuesta(
    tipo: str, concepto: str, pregunta: str, respuesta: str, contexto: str, llm: LLMProvider
) -> dict:
    """
    Evalúa la respuesta del estudiante a una flashcard, ejercicio, pregunta de
    concepto o explicación Feynman, comparándola con el contenido de la BdC.
    Devuelve {"correcto": bool, "feedback": str}.
    """
    if tipo == "feynman":
        # La técnica Feynman busca comprensión, no memorización: si la explicación
        # es una copia casi literal de la BdC, no se da por buena aunque sea correcta.
        criterio = (
            "El estudiante está aplicando la técnica Feynman: tiene que explicar el concepto "
            "con sus propias palabras. Si la explicación es básicamente una copia literal o "
            "casi literal de frases de la BdC, NO la des por correcta aunque el contenido sea "
            "exacto: indica que parece memorizado y pide que lo explique con sus propias "
            "palabras, a ser posible con un ejemplo. Si de verdad lo explica bien (aunque con "
            "otras palabras y sin ser perfecto), da el resultado como correcto."
        )
    else:
        criterio = (
            "Evalúa si la respuesta del estudiante es correcta según el contenido de la BdC. "
            "No hace falta que sea textualmente igual: acepta cualquier formulación que sea "
            "conceptualmente correcta y completa."
        )

    instruccion = (
        f"Eres un profesor corrigiendo a un estudiante. {criterio}\n\n"
        f"CONCEPTO: {concepto}\n"
        f"PREGUNTA: {pregunta}\n"
        f"RESPUESTA DEL ESTUDIANTE: {respuesta}\n\n"
        "Responde EXACTAMENTE en este formato, sin nada más:\n"
        "RESULTADO: correcto|incorrecto\n"
        "FEEDBACK: <feedback breve, 2-3 frases, directo y constructivo>"
    )
    bruto = await llm.generar_texto(instruccion, contexto)

    resultado_m = re.search(r"RESULTADO:\s*(correcto|incorrecto)", bruto, re.IGNORECASE)
    feedback_m = re.search(r"FEEDBACK:\s*(.+)", bruto, re.DOTALL)
    if not resultado_m or not feedback_m:
        raise EstudioError("el modelo no ha devuelto la corrección en el formato esperado.")

    return {
        "correcto": resultado_m.group(1).lower() == "correcto",
        "feedback": feedback_m.group(1).strip(),
    }


# --------------------------------------------------------------------
# Resumen de sesión
# --------------------------------------------------------------------

async def generar_resumen_sesion(interacciones: list, contexto: str, llm: LLMProvider) -> str:
    """
    interacciones: lista de dicts {"tipo", "contenido", "timestamp"}, tal como
    los devuelve Tracker.obtener_interacciones_recientes().
    """
    lineas = [f"- [{i['tipo']}] {i['contenido']}" for i in interacciones if i["contenido"]]
    log_sesion = "\n".join(lineas) if lineas else "(sin detalle disponible, solo interacciones sueltas)"

    instruccion = (
        "Aquí tienes el registro de la sesión de estudio de un estudiante (preguntas hechas, "
        "flashcards y ejercicios respondidos, conceptos explicados...). Escribe un resumen breve "
        "(máximo 6-8 líneas) de qué ha repasado y qué conceptos domina bien, y señala, si es "
        "evidente por el registro, en qué conceptos parece tener más dificultad. Sé concreto y "
        "evita relleno.\n\n"
        f"REGISTRO DE LA SESIÓN:\n{log_sesion}"
    )
    return await llm.generar_texto(instruccion, contexto)