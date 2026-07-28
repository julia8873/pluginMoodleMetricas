# --8<-- [start:file_desc]
"""
Trazabilidad por estudiante.

Usa la base de datos que maubot proporciona automáticamente a cada plugin
(self.database) cuando "database: true" está declarado en maubot.yaml.

Aquí no se guarda el contenido de las conversaciones (eso lo tiene Synapse
en su propio histórico); solo se guardan los EVENTOS de aprendizaje que
interesan para la trazabilidad: qué tipo de acción hizo el estudiante,
cuándo, y un resumen corto (p.ej. la pregunta, o el nombre del fichero).
"""

import time
from typing import Optional

from mautrix.util.async_db import Connection, Database, UpgradeTable

upgrade_table = UpgradeTable()

# --------------------------------------------------------------------
# Migraciones de esquema
# --------------------------------------------------------------------

@upgrade_table.register(description="Crear tablas de trazabilidad (interacciones, fuentes_raw, ejercicios)")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE interacciones (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT    NOT NULL,
            room_id    TEXT    NOT NULL,
            tipo       TEXT    NOT NULL,
            contenido  TEXT,
            timestamp  BIGINT  NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE fuentes_raw (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id     TEXT    NOT NULL,
            room_id        TEXT    NOT NULL,
            nombre_archivo TEXT    NOT NULL,
            ruta_repo      TEXT    NOT NULL,
            timestamp      BIGINT  NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE ejercicios (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT    NOT NULL,
            room_id    TEXT    NOT NULL,
            resultado  TEXT    NOT NULL,
            timestamp  BIGINT  NOT NULL
        )
        """
    )


@upgrade_table.register(description="Añadir columna 'tipo' a ejercicios (flashcard/ejercicio/concepto/feynman)")
async def upgrade_v2(conn: Connection) -> None:
    await conn.execute("ALTER TABLE ejercicios ADD COLUMN tipo TEXT NOT NULL DEFAULT 'ejercicio'")


@upgrade_table.register(description="Crear tabla de dominio de conceptos (!concepto, !flashcard, !feynman, !mapa)")
async def upgrade_v3(conn: Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE conceptos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      TEXT    NOT NULL,
            concepto        TEXT    NOT NULL,
            intentos        INTEGER NOT NULL DEFAULT 0,
            aciertos        INTEGER NOT NULL DEFAULT 0,
            dominado        INTEGER NOT NULL DEFAULT 0,
            ultima_revision BIGINT  NOT NULL,
            UNIQUE (student_id, concepto)
        )
        """
    )


@upgrade_table.register(description="Crear tabla de curación de contenido (subidas, movidos, borrados)")
async def upgrade_v4(conn: Connection) -> None:
    # La curación es distinta de una "interacción de estudio": aquí se registran
    # las aportaciones a la BdC (subir, mover, borrar documentos), que el PDF de
    # trazabilidad pide reportar por separado de las sesiones de repaso.
    await conn.execute(
        """
        CREATE TABLE curaciones (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT    NOT NULL,
            room_id    TEXT    NOT NULL,
            tipo       TEXT    NOT NULL,
            ruta       TEXT,
            timestamp  BIGINT  NOT NULL
        )
        """
    )


@upgrade_table.register(description="Crear tabla qa_historial para registrar preguntas, respuestas y evaluaciones completas")
async def upgrade_v5(conn: Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE qa_historial (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT    NOT NULL,
            room_id    TEXT    NOT NULL,
            tipo       TEXT    NOT NULL,
            pregunta   TEXT    NOT NULL,
            respuesta  TEXT    NOT NULL,
            evaluacion TEXT,
            timestamp  BIGINT  NOT NULL
        )
        """
    )


@upgrade_table.register(description="Dummy upgrade para evitar error de versión v6 adelantada")
async def upgrade_v6(conn: Connection) -> None:
    pass


@upgrade_table.register(description="Sesiones con cierre automático, tabla de estudiantes pseudonimizados y persistencia de resúmenes")
async def upgrade_v7(conn: Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE estudiantes (
            student_id      TEXT    PRIMARY KEY,
            id_pseudo       TEXT    UNIQUE NOT NULL,
            moodle_user_id  INTEGER,
            curso_id        INTEGER
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE sesiones (
            session_id   TEXT    PRIMARY KEY,
            student_id   TEXT    NOT NULL REFERENCES estudiantes(student_id),
            room_id      TEXT    NOT NULL,
            inicio       BIGINT  NOT NULL,
            fin          BIGINT,
            num_eventos  INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE resumenes_sesion (
            session_id       TEXT    PRIMARY KEY REFERENCES sesiones(session_id),
            resumen_texto    TEXT    NOT NULL,
            temas_detectados TEXT,
            dudas_detectadas TEXT,
            generado_en      BIGINT  NOT NULL
        )
        """
    )
    await conn.execute("ALTER TABLE interacciones ADD COLUMN session_id TEXT")
    await conn.execute("ALTER TABLE qa_historial  ADD COLUMN session_id TEXT")


# --------------------------------------------------------------------
# Tracker: envoltorio sobre la base de datos del plugin
# --------------------------------------------------------------------

class Tracker:
    """
    Envoltorio fino sobre self.database para registrar y consultar
    la trazabilidad de cada estudiante (identificado por su user_id de Matrix,
    p.ej. "@julia:mi-matrix-local.dev").
    """

    def __init__(self, db: Database):
        self.db = db

    # --------------------------------------------------------------------
    # Registro de eventos de estudio
    # --------------------------------------------------------------------

    async def log_interaccion(self, student_id: str, room_id: str, tipo: str, contenido: str = "", session_id: Optional[str] = None) -> None:
        """
        Registra una interacción de estudio o comando con el bot.
        Se guardan hasta 4000 caracteres para permitir consultar el historial detallado.
        Acepta session_id opcional para vincular la interacción a la sesión activa.
        """
        await self.db.execute(
            "INSERT INTO interacciones (student_id, room_id, tipo, contenido, timestamp, session_id) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            student_id, room_id, tipo, (contenido or "")[:4000], int(time.time()), session_id,
        )

    async def log_qa(self, student_id: str, room_id: str, tipo: str, pregunta: str, respuesta: str, evaluacion: str = "", session_id: Optional[str] = None) -> None:
        """Registra una pregunta, la respuesta del usuario/bot y su evaluación completa para trazabilidad.
        Acepta session_id opcional para vincular la entrada al ciclo de sesión activo."""
        await self.db.execute(
            "INSERT INTO qa_historial (student_id, room_id, tipo, pregunta, respuesta, evaluacion, timestamp, session_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            student_id, room_id, tipo, (pregunta or "")[:4000], (respuesta or "")[:4000], (evaluacion or "")[:4000], int(time.time()), session_id,
        )

    async def log_fuente_raw(self, student_id: str, room_id: str, nombre_archivo: str, ruta_repo: str) -> None:
        """Se llama cuando el estudiante añade una fuente nueva a la BdC (p.ej. un PDF)."""
        await self.db.execute(
            "INSERT INTO fuentes_raw (student_id, room_id, nombre_archivo, ruta_repo, timestamp) "
            "VALUES ($1, $2, $3, $4, $5)",
            student_id, room_id, nombre_archivo, ruta_repo, int(time.time()),
        )

    async def log_ejercicio(self, student_id: str, room_id: str, resultado: str, tipo: str = "ejercicio") -> None:
        """
        Registra el resultado FINAL de un intento de ejercicio/flashcard/concepto/feynman.
        Solo se llama una vez por intento completado (en _evaluar_pendiente), nunca
        durante el diálogo intermedio, para no penalizar el proceso de repaso.
        """
        await self.db.execute(
            "INSERT INTO ejercicios (student_id, room_id, resultado, tipo, timestamp) VALUES ($1, $2, $3, $4, $5)",
            student_id, room_id, resultado, tipo, int(time.time()),
        )

    async def log_curacion(self, student_id: str, room_id: str, tipo: str, ruta: str = "") -> None:
        """
        Registra una acción de curación del contenido de la BdC.

        tipo: 'subida' (nuevo documento), 'movido' (cambio de carpeta), 'borrado'.
        Esto permite separar en !misestadisticas las aportaciones/ediciones a la BdC
        de las interacciones puramente de estudio (flashcards, ejercicios, etc.),
        como indica el PDF de trazabilidad del proyecto.
        """
        await self.db.execute(
            "INSERT INTO curaciones (student_id, room_id, tipo, ruta, timestamp) VALUES ($1, $2, $3, $4, $5)",
            student_id, room_id, tipo, (ruta or "")[:500], int(time.time()),
        )

    async def registrar_concepto(self, student_id: str, concepto: str, acierto: bool) -> None:
        """
        Actualiza el progreso del estudiante en un concepto concreto. Se llama desde
        !concepto, !flashcard y !feynman al corregir la respuesta.

        "dominado": ≥2 aciertos y ≥60% de aciertos sobre el total de intentos.
        """
        concepto = concepto.strip().lower()
        fila = await self.db.fetchrow(
            "SELECT intentos, aciertos FROM conceptos WHERE student_id = $1 AND concepto = $2",
            student_id, concepto,
        )
        intentos = (fila["intentos"] if fila else 0) + 1
        aciertos = (fila["aciertos"] if fila else 0) + (1 if acierto else 0)
        dominado = 1 if (aciertos >= 2 and aciertos / intentos >= 0.6) else 0

        await self.db.execute(
            """
            INSERT INTO conceptos (student_id, concepto, intentos, aciertos, dominado, ultima_revision)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (student_id, concepto) DO UPDATE SET
                intentos = $3, aciertos = $4, dominado = $5, ultima_revision = $6
            """,
            student_id, concepto, intentos, aciertos, dominado, int(time.time()),
        )

    # --------------------------------------------------------------------
    # Gestión de sesiones (upgrade_v7)
    # --------------------------------------------------------------------

    async def ensure_estudiante(self, student_id: str) -> str:
        """
        Registra el estudiante en 'estudiantes' la primera vez que se le ve
        (lazy insert con ON CONFLICT DO NOTHING).  Genera un UUID interno
        (id_pseudo) que se expone al panel de Moodle sin revelar el Matrix ID.
        Devuelve el id_pseudo del estudiante.
        """
        import uuid
        fila = await self.db.fetchrow(
            "SELECT id_pseudo FROM estudiantes WHERE student_id = $1", student_id
        )
        if fila:
            return fila["id_pseudo"]
        id_pseudo = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO estudiantes (student_id, id_pseudo) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            student_id, id_pseudo,
        )
        fila = await self.db.fetchrow(
            "SELECT id_pseudo FROM estudiantes WHERE student_id = $1", student_id
        )
        return fila["id_pseudo"] if fila else id_pseudo

    async def crear_o_continuar_sesion(self, student_id: str, room_id: str) -> str:
        """
        Devuelve el session_id activo para (student_id, room_id).
        Si no hay sesión abierta (fin IS NULL), crea una nueva con UUID fresco.
        El estudiante se registra en 'estudiantes' si aún no existe (lazy insert).
        """
        import uuid
        await self.ensure_estudiante(student_id)
        fila = await self.db.fetchrow(
            "SELECT session_id FROM sesiones WHERE student_id = $1 AND room_id = $2 AND fin IS NULL",
            student_id, room_id,
        )
        if fila:
            return fila["session_id"]
        session_id = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO sesiones (session_id, student_id, room_id, inicio) VALUES ($1, $2, $3, $4)",
            session_id, student_id, room_id, int(time.time()),
        )
        return session_id

    async def incrementar_eventos_sesion(self, session_id: str) -> None:
        """Incrementa el contador de eventos de una sesión activa."""
        await self.db.execute(
            "UPDATE sesiones SET num_eventos = num_eventos + 1 WHERE session_id = $1",
            session_id,
        )

    async def cerrar_sesion(self, session_id: str) -> None:
        """Marca la sesión como cerrada fijando 'fin' al timestamp actual."""
        await self.db.execute(
            "UPDATE sesiones SET fin = $1 WHERE session_id = $2",
            int(time.time()), session_id,
        )

    async def guardar_resumen_sesion(
        self,
        session_id: str,
        resumen_texto: str,
        temas_detectados: str = "",
        dudas_detectadas: str = "",
    ) -> None:
        """Persiste el resumen generado por generar_resumen_sesion() asociado a la sesión."""
        await self.db.execute(
            """
            INSERT INTO resumenes_sesion (session_id, resumen_texto, temas_detectados, dudas_detectadas, generado_en)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (session_id) DO UPDATE SET
                resumen_texto    = $2,
                temas_detectados = $3,
                dudas_detectadas = $4,
                generado_en      = $5
            """,
            session_id, resumen_texto, temas_detectados or "", dudas_detectadas or "", int(time.time()),
        )

    async def obtener_sesiones_abiertas_inactivas(self, umbral_segundos: int) -> list:
        """
        Devuelve sesiones abiertas (fin IS NULL) sin actividad reciente.
        'Sin actividad' = ninguna interacción vinculada en los últimos umbral_segundos,
        o sesión recién creada sin ninguna interacción y más antigua que el umbral.
        Usado por el detector periódico de inactividad de sesiones.py.
        """
        limite = int(time.time()) - umbral_segundos
        filas = await self.db.fetch(
            """
            SELECT s.session_id, s.student_id, s.room_id, s.inicio
            FROM sesiones s
            WHERE s.fin IS NULL
              AND (
                (
                  SELECT MAX(i.timestamp) FROM interacciones i
                  WHERE i.session_id = s.session_id
                ) < $1
                OR (
                  NOT EXISTS (
                    SELECT 1 FROM interacciones i WHERE i.session_id = s.session_id
                  )
                  AND s.inicio < $1
                )
              )
            """,
            limite,
        )
        return [dict(f) for f in filas]

    async def obtener_interacciones_sesion(self, session_id: str) -> list:
        """Devuelve todas las interacciones de una sesión concreta, en orden cronológico."""
        filas = await self.db.fetch(
            "SELECT tipo, contenido, timestamp FROM interacciones "
            "WHERE session_id = $1 ORDER BY timestamp ASC",
            session_id,
        )
        return [dict(f) for f in filas]

    async def obtener_progreso_para_moodle(self, curso_id: Optional[int] = None) -> list:
        """
        Devuelve, por alumno (usando id_pseudo sin exponer el Matrix ID):
        nº de sesiones, fecha de la última, resumen más reciente y conceptos dominados.
        Filtrable por curso_id.  Esta es la función que consume el puente hacia Moodle.
        """
        if curso_id is not None:
            filas = await self.db.fetch(
                """
                SELECT
                    e.id_pseudo,
                    e.curso_id,
                    COUNT(DISTINCT s.session_id)  AS num_sesiones,
                    MAX(s.inicio)                 AS ultima_sesion,
                    (SELECT rs.resumen_texto FROM resumenes_sesion rs
                     JOIN sesiones s2 ON s2.session_id = rs.session_id
                     WHERE s2.student_id = e.student_id
                     ORDER BY rs.generado_en DESC LIMIT 1) AS ultimo_resumen,
                    (SELECT COUNT(*) FROM conceptos c
                     WHERE c.student_id = e.student_id AND c.dominado = 1) AS conceptos_dominados
                FROM estudiantes e
                LEFT JOIN sesiones s ON s.student_id = e.student_id
                WHERE e.curso_id = $1
                GROUP BY e.id_pseudo, e.curso_id, e.student_id
                ORDER BY ultima_sesion DESC NULLS LAST
                """,
                curso_id,
            )
        else:
            filas = await self.db.fetch(
                """
                SELECT
                    e.id_pseudo,
                    e.curso_id,
                    COUNT(DISTINCT s.session_id)  AS num_sesiones,
                    MAX(s.inicio)                 AS ultima_sesion,
                    (SELECT rs.resumen_texto FROM resumenes_sesion rs
                     JOIN sesiones s2 ON s2.session_id = rs.session_id
                     WHERE s2.student_id = e.student_id
                     ORDER BY rs.generado_en DESC LIMIT 1) AS ultimo_resumen,
                    (SELECT COUNT(*) FROM conceptos c
                     WHERE c.student_id = e.student_id AND c.dominado = 1) AS conceptos_dominados
                FROM estudiantes e
                LEFT JOIN sesiones s ON s.student_id = e.student_id
                GROUP BY e.id_pseudo, e.curso_id, e.student_id
                ORDER BY ultima_sesion DESC NULLS LAST
                """
            )
        return [dict(f) for f in filas]

    async def obtener_ultimo_resumen_sesion_alumno(self, student_id: str) -> Optional[str]:
        """Devuelve el texto del último resumen de sesión generado para el alumno."""
        fila = await self.db.fetchrow(
            """
            SELECT rs.resumen_texto 
            FROM resumenes_sesion rs
            JOIN sesiones s ON s.session_id = rs.session_id
            WHERE s.student_id = $1
            ORDER BY rs.generado_en DESC 
            LIMIT 1
            """,
            student_id
        )
        return fila["resumen_texto"] if fila else None

    async def obtener_historial_conversacion(self, student_id: str, room_id: str, limit: int = 10) -> list:
        """
        Recupera los últimos intercambios de pregunta/respuesta del historial
        para inicializar la memoria de conversación si el bot se reinicia.
        """
        filas = await self.db.fetch(
            """
            SELECT pregunta, respuesta 
            FROM qa_historial 
            WHERE student_id = $1 AND room_id = $2
            ORDER BY timestamp DESC 
            LIMIT $3
            """,
            student_id, room_id, limit
        )
        historial = []
        # Venían en orden descendente, las invertimos para el LLM
        for f in reversed(filas):
            if f["pregunta"]:
                historial.append({"role": "user", "content": f["pregunta"]})
            if f["respuesta"]:
                historial.append({"role": "assistant", "content": f["respuesta"]})
        return historial

    # --------------------------------------------------------------------
    # Purga de datos (retención RGPD/LOPDGDD)
    # --------------------------------------------------------------------

    async def purgar_datos_antiguos(self, retention_days: int) -> dict:
        """
        Borra filas de interacciones y qa_historial más antiguas que retention_days días.
        Los resumenes_sesion se conservan como registro agregado (no se purgan).
        Devuelve un dict con el número de filas borradas de cada tabla.
        NOTA: revisar con el DPD de la UGR antes de activar en producción (RGPD art.5,
        LOPDGDD art.34 — la UGR está obligada a designar DPD como universidad pública).
        """
        limite = int(time.time()) - retention_days * 86400
        await self.db.execute("DELETE FROM interacciones WHERE timestamp < $1", limite)
        await self.db.execute("DELETE FROM qa_historial  WHERE timestamp < $1", limite)
        return {"retention_days": retention_days, "cutoff_timestamp": limite}

    # --------------------------------------------------------------------
    # Búsquedas sobre fuentes_raw
    # --------------------------------------------------------------------

    async def buscar_fuentes_por_nombre(self, patron: str) -> list:
        """
        Usado por !documento para encontrar quién aportó un fichero y cuándo.
        Busca por coincidencia parcial en nombre y ruta para cubrir tanto ficheros
        subidos con su nombre original como los renombrados antes de guardarse.
        """
        filas = await self.db.fetch(
            "SELECT student_id, nombre_archivo, ruta_repo, timestamp FROM fuentes_raw "
            "WHERE nombre_archivo LIKE $1 OR ruta_repo LIKE $1 ORDER BY timestamp DESC",
            f"%{patron}%",
        )
        return [dict(fila) for fila in filas]

    async def actualizar_ruta_fuente(self, ruta_antigua: str, ruta_nueva: str) -> None:
        """
        Se llama tras !mover: actualiza la ruta en fuentes_raw para que !documento
        y futuras búsquedas sigan encontrando el fichero en su nueva ubicación.
        Si el fichero no estaba en la tabla (sembrado por git directamente), no hace nada.
        """
        await self.db.execute(
            "UPDATE fuentes_raw SET ruta_repo = $1 WHERE ruta_repo = $2",
            ruta_nueva, ruta_antigua,
        )

    async def eliminar_fuentes_por_ruta(self, ruta: str) -> None:
        """
        Se llama tras !borrar: quita de fuentes_raw el registro del fichero eliminado
        para no mantener referencias a rutas que ya no existen en el repo.
        """
        await self.db.execute("DELETE FROM fuentes_raw WHERE ruta_repo = $1", ruta)

    # --------------------------------------------------------------------
    # Consulta de métricas
    # --------------------------------------------------------------------

    async def obtener_interacciones_recientes(self, student_id: str, desde_timestamp: int) -> list:
        """Usado por !resumen para reconstruir la actividad de la sesión actual."""
        filas = await self.db.fetch(
            "SELECT tipo, contenido, timestamp FROM interacciones "
            "WHERE student_id = $1 AND timestamp >= $2 ORDER BY timestamp ASC",
            student_id, desde_timestamp,
        )
        return [dict(fila) for fila in filas]

    async def obtener_mapa_conceptos(self, student_id: str) -> list:
        """Usado por !mapa. Devuelve todos los conceptos trabajados, más reciente primero."""
        filas = await self.db.fetch(
            "SELECT concepto, intentos, aciertos, dominado, ultima_revision FROM conceptos "
            "WHERE student_id = $1 ORDER BY ultima_revision DESC",
            student_id,
        )
        return [dict(fila) for fila in filas]

    async def obtener_estadisticas(self, student_id: str) -> dict:
        """
        Agrega todas las métricas de trazabilidad del estudiante para !misestadisticas.
        Incluye interacciones de estudio, fuentes aportadas, ejercicios realizados,
        y acciones de curación de contenido (subidas, movidos, borrados de documentos).
        """
        total_interacciones = await self.db.fetchval(
            "SELECT COUNT(*) FROM interacciones WHERE student_id = $1", student_id
        )
        total_fuentes = await self.db.fetchval(
            "SELECT COUNT(*) FROM fuentes_raw WHERE student_id = $1", student_id
        )
        total_ejercicios = await self.db.fetchval(
            "SELECT COUNT(*) FROM ejercicios WHERE student_id = $1", student_id
        )
        ejercicios_correctos = await self.db.fetchval(
            "SELECT COUNT(*) FROM ejercicios WHERE student_id = $1 AND resultado = 'correcto'",
            student_id,
        )
        ultima_interaccion = await self.db.fetchval(
            "SELECT MAX(timestamp) FROM interacciones WHERE student_id = $1", student_id
        )
        total_curaciones = await self.db.fetchval(
            "SELECT COUNT(*) FROM curaciones WHERE student_id = $1", student_id
        )
        curaciones_subidas = await self.db.fetchval(
            "SELECT COUNT(*) FROM curaciones WHERE student_id = $1 AND tipo = 'subida'", student_id
        )
        curaciones_movidos = await self.db.fetchval(
            "SELECT COUNT(*) FROM curaciones WHERE student_id = $1 AND tipo = 'movido'", student_id
        )
        curaciones_borrados = await self.db.fetchval(
            "SELECT COUNT(*) FROM curaciones WHERE student_id = $1 AND tipo = 'borrado'", student_id
        )

        return {
            "total_interacciones": total_interacciones or 0,
            "total_fuentes_raw": total_fuentes or 0,
            "total_ejercicios": total_ejercicios or 0,
            "ejercicios_correctos": ejercicios_correctos or 0,
            "ultima_interaccion": ultima_interaccion,
            "total_curaciones": total_curaciones or 0,
            "curaciones_subidas": curaciones_subidas or 0,
            "curaciones_movidos": curaciones_movidos or 0,
            "curaciones_borrados": curaciones_borrados or 0,
        }

    async def obtener_todas_interacciones(self, student_id: str, limite: int = 50) -> list:
        """Devuelve el historial cronológico de interacciones de un estudiante."""
        filas = await self.db.fetch(
            "SELECT tipo, contenido, timestamp FROM interacciones "
            "WHERE student_id = $1 ORDER BY timestamp DESC LIMIT $2",
            student_id, limite,
        )
        return [dict(f) for f in filas]

    async def obtener_todas_qa(self, student_id: str, limite: int = 30) -> list:
        """Devuelve el historial completo de preguntas, respuestas y evaluaciones."""
        filas = await self.db.fetch(
            "SELECT tipo, pregunta, respuesta, evaluacion, timestamp FROM qa_historial "
            "WHERE student_id = $1 ORDER BY timestamp DESC LIMIT $2",
            student_id, limite,
        )
        return [dict(f) for f in filas]

    async def obtener_todas_curaciones(self, student_id: str, limite: int = 50) -> list:
        """Devuelve el historial de curación (subidas, movidos, borrados) en la BdC."""
        filas = await self.db.fetch(
            "SELECT tipo, ruta, timestamp FROM curaciones "
            "WHERE student_id = $1 ORDER BY timestamp DESC LIMIT $2",
            student_id, limite,
        )
        return [dict(f) for f in filas]
# --8<-- [end:file_desc]
