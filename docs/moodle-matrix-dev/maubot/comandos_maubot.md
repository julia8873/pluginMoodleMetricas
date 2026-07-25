# Comandos de LLM Wiki Assistant (Maubot)

A continuación se detalla la lista completa de comandos disponibles en las salas de Matrix donde esté invitado el bot asistente. Puedes enviar cualquiera de estos comandos en el chat para interactuar con tu Base de Conocimiento (BdC) y realizar sesiones de estudio.

---

## Gestión de la Base de Conocimiento (OKF)

| Comando | Descripción |
| :--- | :--- |
| `!ficheros` | **Lista el árbol completo** de archivos `.md` y `.txt` disponibles en el repositorio Git vinculado a la asignatura. |
| `!documento <nombre>` | Muestra información detallada sobre un archivo concreto, incluyendo su contenido y el historial de cambios (commits). |
| `!carpeta` | Comando base para gestionar la jerarquía de carpetas/asignaturas de la BdC. |
| `!mover <nombre> -> <destino>`| **Mueve un documento** de su ubicación actual a una nueva carpeta. Si quieres moverlo a la raíz, usa `raiz` como destino. |
| `!borrar <nombre>` | **Elimina un documento** de la base de conocimiento (requiere confirmación previa para evitar borrados accidentales). |
| `!ingest_lotes [tema:X]` | Fuerza la extracción completa de conceptos por lotes desde los archivos en bruto (`raw/`) que se hayan adjuntado. |
| `!crear_conceptos` | Extrae automáticamente términos, preguntas y apuntes a partir del material no estructurado subido a la sala de chat. |

*(**Nota:** Además de usar comandos, puedes simplemente **adjuntar archivos Markdown, PDFs o imágenes** en el chat y el bot procesará automáticamente la ingesta del material si la opción `ingest_automatico` está activa).*

---

## Estudio, Repaso y Comprensión

| Comando | Descripción |
| :--- | :--- |
| `!estudio` | Inicia una **sesión de estudio interactiva guiada por IA**. El bot te hará preguntas de comprensión sobre tus apuntes para asentar conocimientos. |
| `!estudio saltar` | Omite la pregunta actual de la sesión de estudio y pasa al siguiente concepto. |
| `!repaso` | Comienza una **sesión de repaso de conceptos** que ya estudiaste previamente, usando técnicas de repetición espaciada. |
| `!repaso saltar` | Omite el concepto actual en el repaso. |
| `!resumen` | Genera un **resumen del rendimiento** y los conceptos que has abordado en la sesión de estudio/repaso actual. |
| `!mapa` | Analiza tu progreso y te dice **qué conceptos dominas** y en cuáles necesitas hacer más hincapié. |

---

## Estadísticas y Trazabilidad

| Comando | Descripción |
| :--- | :--- |
| `!trazabilidad` | Consulta todo tu **historial de aprendizaje y curación** de contenidos en Matrix/Moodle. |
| `!misestadisticas` | Muestra un resumen numérico de tus métricas personales en la plataforma. |

---

## Mantenimiento y Organización

| Comando | Descripción |
| :--- | :--- |
| `!organizacion` | Analiza el estado del repositorio y **propone reorganizaciones** para mejorar la estructura de tu formato OKF. |
| `!organizacion aplicar`| **Aplica automáticamente los cambios** estructurales sugeridos en el paso anterior. |

---

## Otros

| Comando | Descripción |
| :--- | :--- |
| `!ayuda` | Despliega en el chat una lista resumida con todos los comandos básicos soportados por el bot. |