import re

PENDIENTE_TTL_SEGUNDOS = 30 * 60
CONFIRMACION_BORRADO_TTL_SEGUNDOS = 5 * 60
SESION_VENTANA_SEGUNDOS = 3 * 60 * 60      # Ventana de !resumen bajo demanda (3 h) — no tocar
SESION_INACTIVIDAD_SEGUNDOS = 30 * 60      # Cierre automático de sesión por inactividad (30 min)
SESION_DETECTOR_INTERVALO_SEGUNDOS = 600   # Cada cuánto corre el detector de inactividad (10 min)
RETENTION_DAYS_DEFAULT = 365               # Días de retención por defecto (revisar con DPD)
HISTORIAL_MAX_TURNOS = 20                  # Máx. turnos user/assistant que se pasan al LLM (10 intercambios)
MAX_CONCEPTOS_REPASO_TEMA = 25
MAX_CONCURRENCIA_GITHUB = 5

FICHEROS_EXCLUIDOS_CONTEXTO = {"agents.md", "index.md", "log.md", "readme.md", "welcome.md"}

AGENTS_MD_PATH = "AGENTS.md"
OKF_LOG_PATH = "okf/log.md"

PATRON_RENOMBRAR = re.compile(r"^(?:nombre|renombrar)\s*:?\s+(.+)$", re.IGNORECASE)
PATRON_TEMA = re.compile(r"\btema:(\S+)", re.IGNORECASE)
PATRON_TIPO = re.compile(r"\btipo:(\S+)", re.IGNORECASE)
