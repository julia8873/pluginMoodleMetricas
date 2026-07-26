# Comandos de LLM Wiki Assistant (Maubot)

A continuación se detalla la lista completa de comandos dispnibles para el llm wiki assistant.

---

## Gestión de la Base de Conocimiento (OKF)

| Comando | Descripción |
| :--- | :--- |
| `!ficheros` | **Lista el árbol completo** de archivos `.md` y `.txt` disponibles en el repositorio Git vinculado a la asignatura. |
| `!documento <nombre>` | **Muestra información detallada** sobre un archivo concreto, incluyendo su contenido y el historial de cambios (commits). |
| `!carpeta` | Comando base para **gestionar la jerarquía de carpetas/asignaturas** de la BdC. |
| `!mover <nombre> -> <destino>`| **Mueve un documento** de su ubicación actual a una nueva carpeta. Si quieres moverlo a la raíz, usa `raiz` como destino. |
| `!borrar <nombre>` | **Elimina un documento** de la base de conocimiento. |
| `!ingest_lotes [tema:X]` | Fuerza la extracción completa de conceptos por lotes desde los archivos en `raw/`. |
| `!crear_conceptos` | **Extrae términos, preguntas y apuntes** a partir del material subido a la sala de chat. |

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