"""
Cliente HTTP genérico compatible con la API de chat completions de OpenAI.

La misma clase LLMProvider funciona con cualquier proveedor que exponga
la interfaz OpenAI (Gemini, OpenAI, Groq, Mistral, DeepSeek, Ollama local,
OpenRouter...) cambiando solo base_url, api_key y model en la configuración.

Se mantiene separado de bot.py para que los prompts y la lógica de red
no estén mezclados con la lógica de Matrix y GitHub.
"""

import asyncio
import re

import aiohttp

# --------------------------------------------------------------------
# Limpieza del razonamiento interno de modelos "thinking"
# --------------------------------------------------------------------

# Algunos modelos razonadores (DeepSeek-R1, Qwen3-thinking, QwQ...) incluyen su
# cadena de razonamiento dentro del campo "content" de la respuesta, delimitada
# por <think>...</think>. Según el proveedor, a veces llega la etiqueta de apertura
# y a veces solo el cierre </think> (porque el proveedor añade el prefijo en la
# plantilla de chat y el campo content solo recibe lo que viene después del <think>
# inicial). Estos dos patrones cubren ambos casos.
_PATRON_THINK_COMPLETO = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_PATRON_THINK_SOLO_CIERRE = re.compile(r"^.*?</think>", re.IGNORECASE | re.DOTALL)


def _quitar_razonamiento(texto: str) -> str:
    """
    Elimina el bloque de razonamiento interno del modelo si se ha colado en el
    texto de respuesta, conservando solo lo que viene después del </think>.
    Si el texto no tiene ninguna etiqueta </think>, se devuelve tal cual.

    El fallback al texto original cubre el caso en que el modelo se queda sin
    tokens durante el razonamiento y nunca escribe la respuesta final: mejor
    devolver el razonamiento parcial que una cadena vacía.
    """
    if not texto:
        return texto
    texto_limpio = _PATRON_THINK_COMPLETO.sub("", texto)
    if "</think>" in texto_limpio.lower():
        texto_limpio = _PATRON_THINK_SOLO_CIERRE.sub("", texto_limpio, count=1)
    texto_limpio = texto_limpio.strip()
    return texto_limpio or texto.strip()


# --------------------------------------------------------------------
# Cliente LLM
# --------------------------------------------------------------------

class LLMProvider:
    """
    Cliente genérico compatible con la API de OpenAI (chat completions).
    Sirve para Gemini, OpenAI, Groq, Mistral, DeepSeek, Ollama local, etc.,
    simplemente cambiando base_url, api_key y model en la configuración.
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    # Reintentos ante 429 (límite de peticiones). Habitual con modelos ":free" de
    # OpenRouter, donde el cupo se comparte entre todos los usuarios del modelo.
    # Backoff exponencial: 3 s, 6 s, 12 s.
    MAX_REINTENTOS_429 = 3
    ESPERA_BASE_429_SEGUNDOS = 3

    # Timeout explícito. Sin esto, aiohttp usa 5 minutos por defecto, lo que dejaría
    # al estudiante sin respuesta ni mensaje de error varios minutos si el backend
    # está colgado (p.ej. Ollama interno con problemas de conectividad).
    TIMEOUT_SEGUNDOS = 90

    # Patrones que identifican un 429 por cuota AGOTADA (diaria/mensual) en vez de
    # por límite de ráfaga temporal. Reintentar con backoff no ayuda si la cuota
    # no se libera en segundos: se falla inmediatamente con mensaje claro.
    _PATRONES_429_NO_REINTENTABLE = ("per-day", "per-month", "daily", "monthly")

    # --------------------------------------------------------------------
    # Envío genérico a /chat/completions
    # --------------------------------------------------------------------

    async def _chat(self, messages: list, max_tokens: int = None) -> str:
        """
        Envía la lista de mensajes al endpoint /chat/completions y devuelve el
        texto de respuesta del modelo. Lo comparten preguntar(), transcribir_imagen()
        y generar_texto() para no duplicar el bloque de petición HTTP.

        max_tokens: si no se especifica, algunos proveedores (p.ej. OpenRouter)
        asumen el máximo del modelo, lo que puede hacer fallar la petición por
        crédito insuficiente aunque la respuesta real sea corta.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        url = f"{self.base_url}/chat/completions"
        timeout = aiohttp.ClientTimeout(total=self.TIMEOUT_SEGUNDOS)

        for intento in range(self.MAX_REINTENTOS_429 + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload, headers=headers) as resp:

                        if resp.status == 429:
                            error_text = await resp.text()
                            if any(p in error_text.lower() for p in self._PATRONES_429_NO_REINTENTABLE):
                                # Cuota diaria/mensual agotada: reintentar no ayuda.
                                raise RuntimeError(
                                    "Se ha agotado la cuota gratuita del modelo por hoy "
                                    f"(el proveedor responde: {error_text}). Prueba de nuevo "
                                    "mañana, añade crédito/cupo en el proveedor, o cambia de "
                                    "modelo en la configuración del bot."
                                )
                            if intento < self.MAX_REINTENTOS_429:
                                # Límite de ráfaga temporal: esperar y reintentar.
                                espera = self.ESPERA_BASE_429_SEGUNDOS * (2 ** intento)
                                await asyncio.sleep(espera)
                                continue
                            raise RuntimeError(f"Error al consultar el modelo (429): {error_text}")

                        if resp.status != 200:
                            error_text = await resp.text()
                            raise RuntimeError(f"Error al consultar el modelo ({resp.status}): {error_text}")

                        data = await resp.json()
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"El backend LLM no ha respondido en {self.TIMEOUT_SEGUNDOS}s (timeout). "
                    "Puede ser un problema de conectividad con el servidor del modelo."
                )

            try:
                # Ruta estándar de la API OpenAI: data -> choices -> [0] -> message -> content.
                contenido = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                raise RuntimeError("El modelo no devolvió una respuesta válida.")

            return _quitar_razonamiento(contenido)

    # --------------------------------------------------------------------
    # Métodos de alto nivel para cada caso de uso
    # --------------------------------------------------------------------

    async def preguntar(self, pregunta: str, contexto: str) -> str:
        """
        Responde una pregunta basándose únicamente en el contexto proporcionado
        (contenido de la BdC). A diferencia de generar_texto(), los errores del
        LLM se devuelven como texto de respuesta en vez de propagarse como excepción,
        porque !pregunta siempre debe responder algo al estudiante.
        """
        system_prompt = (
            "Eres un asistente que responde ÚNICAMENTE usando la documentación "
            "proporcionada a continuación. Si la respuesta no está en la documentación, "
            "responde exactamente: 'No tengo esa información en la documentación del repositorio.' "
            "No inventes información ni uses conocimiento externo.\n\n"
            f"DOCUMENTACIÓN:\n{contexto}"
        )
        try:
            return await self._chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta},
            ])
        except RuntimeError as exc:
            return str(exc)

    # Tope de tokens de salida para transcribir una única página/imagen. Una página de
    # apuntes manuscritos densa no debería superar unos pocos miles de tokens en Markdown;
    # este límite evita depender del máximo por defecto del modelo (65 536 en algunos
    # casos), que en OpenRouter puede hacer fallar la petición por crédito insuficiente.
    MAX_TOKENS_TRANSCRIPCION = 4096

    async def transcribir_imagen(self, imagen_base64: str, mime_type: str) -> str:
        """
        Transcribe una imagen (foto de apuntes manuscritos, o página de PDF escaneado
        ya renderizada) usando el LLM multimodal configurado. Requiere un modelo que
        admita entrada de imagen (Gemini, GPT-4o, etc.); no funciona con solo-texto.

        El system_prompt insiste en no "inventar" símbolos o fórmulas conocidas en lugar
        de leer los trazos reales, que es el error más habitual con letra matemática
        manuscrita y la razón por la que tenemos un modelo de visión separado.
        """
        system_prompt = (
            "Eres un transcriptor de apuntes universitarios manuscritos. "
            "Tu única tarea es transcribir FIELMENTE el texto de la imagen a Markdown, "
            "sin resumir, sin corregir el contenido y sin añadir comentarios, valoraciones "
            "ni explicaciones propias. "
            "IMPORTANTE: no sustituyas ninguna fórmula, función o símbolo por un ejemplo "
            "\"típico\" o \"conocido\" que te recuerde, aunque la letra sea difícil de leer y "
            "el resultado que veas no encaje con ningún ejemplo estándar de manual. Transcribe "
            "EXACTAMENTE los trazos que hay en la imagen, símbolo a símbolo, incluso si el "
            "contenido resultante te parece inusual o poco convencional. Sustituir contenido "
            "real por un ejemplo que recuerdes de tu entrenamiento es el error más grave que "
            "puedes cometer en esta tarea. "
            "Usa LaTeX (entre $...$ para fórmulas en línea, $$...$$ para fórmulas destacadas) "
            "para cualquier notación matemática. "
            "Conserva la estructura visible (títulos, apartados, listas, numeración) usando "
            "sintaxis Markdown equivalente. "
            "Si hay un dibujo o diagrama que no se puede transcribir como texto, descríbelo "
            "brevemente entre corchetes, por ejemplo: [Diagrama: esquema de fuerzas sobre un plano inclinado]. "
            "Si alguna palabra o símbolo es realmente ilegible, indícalo con [¿ilegible?] en vez de "
            "inventarlo o de rellenarlo con lo que \"tendría sentido\" que pusiera ahí. "
            "Devuelve únicamente la transcripción, sin ningún texto introductorio ni de cierre."
        )
        return await self._chat([
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe esta página de apuntes."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{imagen_base64}"},
                    },
                ],
            },
        ], max_tokens=self.MAX_TOKENS_TRANSCRIPCION)

    async def generar_texto(self, instruccion: str, contexto: str) -> str:
        """
        Método genérico para las herramientas de estudio (flashcards, ejercicios,
        técnica Feynman, búsqueda de ejercicios, resumen de sesión...): instruccion
        define la tarea concreta y contexto es el contenido de la BdC en el que debe
        basarse. Propaga RuntimeError si el LLM falla, para que cada comando decida
        cómo informar al estudiante.
        """
        system_prompt = f"{instruccion}\n\nContenido de la BdC de referencia:\n{contexto}"
        return await self._chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Adelante."},
        ])