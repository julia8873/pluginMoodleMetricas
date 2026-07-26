import math
import re
from collections import Counter

class BuscadorTFIDF:
    """
    Motor de búsqueda semántica de coste cero basado en TF-IDF y Similitud del Coseno.
    Permite encontrar los fragmentos más relevantes de la Base de Conocimiento
    sin necesidad de usar bases de datos vectoriales (ChromaDB) ni embeddings.
    """
    def __init__(self):
        self.documentos = []  # Lista de tuplas (texto_original, tokens)
        self.idf = {}
        self.total_docs = 0
        self.chunk_size = 500  # Caracteres por chunk

    def _limpiar_texto(self, texto: str) -> list[str]:
        """Convierte a minúsculas, quita puntuación y devuelve palabras sueltas sin stopwords."""
        texto = texto.lower()
        texto = re.sub(r'[^\w\s]', '', texto)
        tokens = texto.split()
        stopwords = {"el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "pero", "si", "no", "de", "del", "a", "al", "en", "por", "para", "con", "sin", "sobre", "que", "qué", "cual", "cuál", "como", "cómo", "es", "son", "fue", "ser", "estar", "esta", "este", "estos", "estas", "se", "su", "sus", "lo", "le", "les"}
        return [t for t in tokens if t not in stopwords]

    def _crear_chunks(self, texto_completo: str) -> list[str]:
        """Divide un texto gigante en párrafos o chunks de tamaño fijo."""
        # Primero dividimos por doble salto de línea (párrafos)
        parrafos = [p.strip() for p in texto_completo.split('\n\n') if p.strip()]
        chunks = []
        chunk_actual = ""
        
        for p in parrafos:
            if len(chunk_actual) + len(p) < self.chunk_size:
                chunk_actual += p + "\n\n"
            else:
                if chunk_actual:
                    chunks.append(chunk_actual.strip())
                # Si un solo párrafo es más grande que el chunk, lo guardamos entero
                if len(p) >= self.chunk_size:
                    chunks.append(p)
                    chunk_actual = ""
                else:
                    chunk_actual = p + "\n\n"
                    
        if chunk_actual:
            chunks.append(chunk_actual.strip())
            
        return chunks

    def indexar(self, texto_bdc: str):
        """Calcula el TF-IDF de todos los chunks de la base de conocimiento."""
        chunks = self._crear_chunks(texto_bdc)
        self.documentos = []
        df = Counter()
        self.total_docs = len(chunks)
        
        # 1. Calcular Document Frequency (DF)
        for chunk in chunks:
            tokens = self._limpiar_texto(chunk)
            self.documentos.append((chunk, tokens))
            palabras_unicas = set(tokens)
            for palabra in palabras_unicas:
                df[palabra] += 1
                
        # 2. Calcular Inverse Document Frequency (IDF)
        self.idf = {}
        for palabra, frec in df.items():
            self.idf[palabra] = math.log((1 + self.total_docs) / (1 + frec)) + 1

    def _calcular_tf(self, tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        total = len(tokens)
        if total == 0:
            return {}
        return {palabra: cuenta / total for palabra, cuenta in tf.items()}

    def _calcular_vector(self, tokens: list[str]) -> dict[str, float]:
        tf = self._calcular_tf(tokens)
        vector = {}
        for palabra, valor_tf in tf.items():
            valor_idf = self.idf.get(palabra, math.log((1 + self.total_docs) / 1) + 1)
            vector[palabra] = valor_tf * valor_idf
        return vector

    def _similitud_coseno(self, v1: dict[str, float], v2: dict[str, float]) -> float:
        interseccion = set(v1.keys()) & set(v2.keys())
        numerador = sum([v1[x] * v2[x] for x in interseccion])
        
        suma1 = sum([val**2 for val in v1.values()])
        suma2 = sum([val**2 for val in v2.values()])
        denominador = math.sqrt(suma1) * math.sqrt(suma2)
        
        if not denominador:
            return 0.0
        else:
            return float(numerador) / denominador

    def buscar(self, query: str, top_k: int = 4) -> str:
        """
        Busca los top_k chunks más relevantes para la query y los devuelve
        concatenados en un único string de contexto.
        """
        if self.total_docs == 0:
            return ""
            
        tokens_query = self._limpiar_texto(query)
        vector_query = self._calcular_vector(tokens_query)
        
        puntuaciones = []
        for chunk, tokens_doc in self.documentos:
            vector_doc = self._calcular_vector(tokens_doc)
            similitud = self._similitud_coseno(vector_query, vector_doc)
            puntuaciones.append((similitud, chunk))
            
        # Ordenar de mayor a menor similitud
        puntuaciones.sort(key=lambda x: x[0], reverse=True)
        
        # Quedarnos solo con los top_k y aquellos que tengan al menos algo de similitud (>0)
        resultados = [chunk for sim, chunk in puntuaciones[:top_k] if sim > 0.01]
        
        if not resultados:
            # Fallback: si no hay ninguna coincidencia (por ejemplo palabras muy raras),
            # devolvemos los primeros párrafos genéricos para que al menos tenga algo
            resultados = [chunk for _, chunk in self.documentos[:top_k]]
            
        return "\n\n...\n\n".join(resultados)
