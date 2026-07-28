# --8<-- [start:file_desc]
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
        """
        is_local = any(loc in self.base_url for loc in ("://localhost", "://127.0.0.1", "://0.0.0.0", "://host.docker.internal", "://ollama", "ugr.es"))
        if not is_local and (not self.api_key or not self.api_key.strip()):
            raise RuntimeError(
                "No se ha configurado la clave API del LLM (llm_api_key o llm_vision_api_key están vacíos). "
                "Por favor, configura tu clave API en base-config.yaml o en los ajustes del bot."
            )

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

                        if resp.status == 429 or resp.status == 413:
                            error_text = await resp.text()
                            if "rate_limit_exceeded" in error_text or "too large" in error_text.lower() or any(p in error_text.lower() for p in self._PATRONES_429_NO_REINTENTABLE):
                                # Cuota diaria/mensual agotada o request individual demasiado grande
                                if "tokens per minute" not in error_text.lower() and "tpm" not in error_text.lower():
                                    raise RuntimeError(
                                        "Se ha agotado la cuota gratuita del modelo o el tamaño de la petición excede el máximo permitido. "
                                        f"(el proveedor responde: {error_text})."
                                    )
                            
                            if intento < self.MAX_REINTENTOS_429:
                                # Límite de ráfaga temporal o TPM alcanzado temporalmente: esperar y reintentar.
                                # Groq tiene límites muy estrictos de TPM en la capa gratuita.
                                espera = self.ESPERA_BASE_429_SEGUNDOS * (3 ** intento)  # backoff más agresivo (3, 9, 27)
                                await asyncio.sleep(espera)
                                continue
                            raise RuntimeError(f"Error de límite de cuota al consultar el modelo ({resp.status}): {error_text}")

                        if resp.status != 200:
                            error_text = await resp.text()
                            raise RuntimeError(f"Error al consultar el modelo ({resp.status}): {error_text}")

                        data = await resp.json()
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"El backend LLM no ha respondido en {self.TIMEOUT_SEGUNDOS}s (timeout). "
                    "Puede ser un problema de conectividad con el servidor del modelo."
                )
            except Exception as exc: # Catch DNS and connection errors
                raise RuntimeError(f"Error de conexión con el LLM: {exc}. ¿La IP/dominio es accesible?")


            try:
                # Ruta estándar de la API OpenAI: data -> choices -> [0] -> message -> content.
                contenido = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                raise RuntimeError("El modelo no devolvió una respuesta válida.")

            return _quitar_razonamiento(contenido)

    # --------------------------------------------------------------------
    # Métodos de alto nivel para cada caso de uso
    # --------------------------------------------------------------------

    def _truncar_contexto(self, contexto: str, max_chars: int = 20000) -> str:
        """
        Trunca el contexto para evitar errores 413 (Payload Too Large) o 
        superar límites de Tokens por Minuto (TPM) en APIs gratuitas (ej. Groq).
        20.000 caracteres equivalen aprox a 5.000 tokens.
        """
        if not contexto:
            return contexto
        if len(contexto) > max_chars:
            aviso = "\n\n[... AVISO: El contenido de la BdC es demasiado grande y se ha truncado para ajustarse al límite de memoria del modelo. Solo se leerá una parte ...]"
            return contexto[:max_chars - len(aviso)] + aviso
        return contexto

    async def preguntar(self, pregunta: str, contexto: str, historial: list | None = None) -> str:
        """
        Responde una pregunta basándose únicamente en el contexto proporcionado
        (contenido de la BdC). Si el contexto es demasiado grande, usa TF-IDF 
        para recuperar los fragmentos más relevantes.
        Acepta historial opcional de turnos previos [{role, content}] para 
        mantener la coherencia de la conversación.
        """
        if len(contexto) > 15000:
            from .buscador import BuscadorTFIDF
            buscador = BuscadorTFIDF()
            buscador.indexar(contexto)
            contexto = buscador.buscar(pregunta, top_k=8)
        else:
            contexto = self._truncar_contexto(contexto, max_chars=15000)

        system_prompt = (
            "Eres un asistente de estudio que responde basándose ÚNICAMENTE en dos fuentes:\n"
            "1. La documentación de la asignatura proporcionada a continuación.\n"
            "2. El historial reciente de la conversación con el usuario.\n\n"
            "No inventes información ni uses conocimiento externo. Si la pregunta pide varios datos "
            "y solo algunos aparecen en tus fuentes, DEBES responder con toda la información "
            "relevante que SÍ esté presente y aclarar qué parte falta.\n\n"
            "Solo si el tema consultado está COMPLETAMENTE AUSENTE de la documentación y de la conversación previa, "
            "responde exactamente: 'No tengo esa información en la documentación ni en nuestra conversación reciente.'\n\n"
            f"DOCUMENTACIÓN:\n{self._truncar_contexto(contexto)}"
        )
        messages = [{"role": "system", "content": system_prompt}]
        if historial:
            messages.extend(historial)
        messages.append({"role": "user", "content": pregunta})
        try:
            return await self._chat(messages)
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
        técnica Feynman, búsqueda de ejercicios, resumen de sesión...).
        Si el contexto es gigante, usa TF-IDF basado en la instrucción para filtrar.
        """
        if len(contexto) > 15000:
            from .buscador import BuscadorTFIDF
            buscador = BuscadorTFIDF()
            buscador.indexar(contexto)
            contexto = buscador.buscar(instruccion, top_k=10)
        else:
            contexto = self._truncar_contexto(contexto, max_chars=15000)

        system_prompt = f"{instruccion}\n\nContenido de la BdC de referencia:\n{contexto}"
        return await self._chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Adelante."},
        ])

    async def evaluar_necesidad_bdc(self, mensaje: str) -> bool:
        """
        Evalúa si un mensaje de texto libre requiere consultar la BdC o si es pura
        conversación (saludos, agradecimientos, bromas).
        """
        system_prompt = (
            "Eres un clasificador de intenciones. El usuario te ha enviado un mensaje. "
            "Tu tarea es decidir si necesitas consultar los apuntes del alumno para responder.\n"
            "Reglas:\n"
            "- Si es puramente un saludo ('hola'), despedida, agradecimiento ('gracias') o pregunta genérica sobre tus funciones ('qué puedes hacer'): responde 'NO'.\n"
            "- Si es una duda académica, o el usuario te pide un resumen de tus conocimientos, temas, o te pregunta qué sabes: responde 'SI'.\n"
            "Responde ÚNICAMENTE con la palabra 'SI' o la palabra 'NO'."
        )
        try:
            respuesta = await self._chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": mensaje},
            ], max_tokens=10)
            # Limpiar puntuación y espacios
            texto_limpio = "".join(c for c in respuesta.lower() if c.isalnum() or c.isspace()).strip()
            # Devolver True solo si la primera palabra es "si"
            return texto_limpio.startswith("si")
        except RuntimeError as exc:
            raise exc # Bubble up the connection error instead of falling back to True

    async def conversar(self, mensaje: str, historial: list | None = None) -> str:
        """
        Responde a mensajes generales que no requieren BdC (saludos, despedidas...).
        Acepta historial opcional de turnos previos [{role, content}] para
        que el LLM recuerde lo que el alumno dijo antes en la misma sesión.
        """
        system_prompt = (
            "Eres el asistente virtual de docencia de MoodleMetricas. "
            "Tienes acceso al historial de chat y al resumen de la sesión anterior, pero debes tratar esta información como CONTEXTO PASIVO.\n\n"
            "DIRECTRICES DE RESPUESTA:\n"
            "1. Eres un asistente de docencia, directo y profesional. Tu función es ayudar con la asignatura.\n"
            "2. NUNCA menciones proactively el historial ni digas cosas como 'recuerdo que hablamos de...', 'como dijimos antes' o '¿quieres retomar el tema?'. "
            "Usa la memoria solo de forma invisible (por ejemplo, si te preguntan '¿cómo me llamo?', respondes con el nombre porque lo sabes, pero sin hacer alusión a que lo leíste en el historial).\n"
            "3. Mantén un tono educado y al grano. Si el usuario te saluda, responde de forma natural y breve ('Hola [Nombre], ¿en qué te puedo ayudar hoy?'), sin ofrecer cháchara ni sacar temas pasados.\n"
            "4. Usa ÚNICAMENTE la Base de Conocimiento y el historial. No te inventes información externa.\n\n"
            "Si te preguntan cuáles son tus funciones, responde que puedes resolver dudas (BdC), generar flashcards, ejercicios y repasos."
        )
        messages = [{"role": "system", "content": system_prompt}]
        if historial:
            messages.extend(historial)
        messages.append({"role": "user", "content": mensaje})
        try:
            return await self._chat(messages)
        except RuntimeError as exc:
            return str(exc)
# --8<-- [end:file_desc]
