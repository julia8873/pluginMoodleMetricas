# pluginMoodleMetricas

Plugin de bloque para Moodle que analiza un repositorio GitHub con estructura OKF y muestra métricas cuantitativas de la Base de Conocimiento.

| Componente | Descripción |
|---|---|
| [`gitmetrics/`](./gitmetrics/README.md) | Plugin de bloque para Moodle: análisis de repositorios GitHub con estructura OKF |
| [`moodle-matrix-dev/`](./moodle-matrix-dev/README.md) | Entorno Docker local con Moodle, MariaDB, Synapse (Matrix), Element Web y Ollama |

---

## Requisitos previos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y corriendo
- WSL (Windows Subsystem for Linux) con Ubuntu
- Git clonado en: `/mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas`

---

## Puesta en marcha

### Opción A — Ejecutar todo automáticamente (Recomendado)

Dispones del guion automatizado `instalar.sh` que levanta Docker, espera a Moodle, copia el plugin, asigna permisos y actualiza la base de datos de un solo golpe:

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas
./instalar.sh
```

Al terminar, verás en la terminal el siguiente resumen con los datos exactos para entrar y añadir el bloque:

```text
------------------------------------------------------------------------------
 ¡TODO LISTO! EL ENTORNO Y EL PLUGIN ESTÁN OPERATIVOS
------------------------------------------------------------------------------

 Moodle URL  : http://localhost:8000
 Usuario     : admin
 Contraseña  : adminpass123

 Pasos para probar el bloque en Moodle:
    1. Abre http://localhost:8000 e inicia sesión.
    2. Entra a un curso -> haz clic en 'Activar edición' (Turn editing on).
    3. Haz clic en 'Añadir un bloque' (Add a block) -> selecciona:
       - En inglés (idioma por defecto de Moodle): 'Git Knowledge Base Metrics'
       - En español: 'Métricas de Base de Conocimiento Git'
    4. Configura el bloque con el repo: https://github.com/julia8873/bdc-prueba
------------------------------------------------------------------------------
```

---

### Opción B — Paso a paso manual

#### PASO 1 — Levantar el entorno Docker

```bash
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev
docker compose up -d
```

### PASO 2 — Esperar a que Moodle arranque

```bash
docker compose logs -f moodle
```

Espera hasta ver esta línea y pulsa **Ctrl+C**:

```
** Moodle setup finished! **
```

> La primera vez puede tardar 2-3 minutos.

### PASO 3 — Copiar el plugin dentro del contenedor

```bash
docker cp \
  /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/gitmetrics \
  moodle-app:/bitnami/moodle/blocks/gitmetrics
```

### PASO 4 — Ajustar permisos

```bash
docker exec --user root moodle-app \
  chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics

docker exec --user root moodle-app \
  chmod -R 755 /bitnami/moodle/blocks/gitmetrics
```

### PASO 5 — Instalar el plugin en Moodle

```bash
docker exec --user daemon moodle-app \
  php /bitnami/moodle/admin/cli/upgrade.php --non-interactive
```

Debes ver al final:

```
-->block_gitmetrics
++ Success ...
```

### PASO 6 — Abrir Moodle y añadir el bloque

1. Abre `http://localhost:8000`
2. Inicia sesión: usuario `admin`, contraseña `adminpass123`
3. Entra en un curso → **Activar edición** (`Turn editing on`) → **Añadir un bloque** (`Add a block`) → selecciona:
   - En inglés (idioma por defecto en Moodle): **Git Knowledge Base Metrics**
   - En español: **Métricas de Base de Conocimiento Git**
4. Haz clic en el engranaje del bloque → **Configurar**
5. Pega la URL del repositorio: `https://github.com/julia8873/bdc-prueba`
6. Guarda → las métricas aparecen automáticamente

---

## Visualización en Asignaturas y Página Completa (100% del ancho)

Hemos integrado el plugin para que actúe como elemento central en las asignaturas del profesor:

### 1. Asignatura dedicada: 'Panel de Métricas y BdC' (Creada automáticamente)
Al ejecutar `./instalar.sh`, se crea automáticamente una asignatura dedicada llamada **Panel de Métricas y BdC** (ID 4) con el bloque preconfigurado para evaluar repositorios de GitHub.
- **Cómo acceder**: Entra en `http://localhost:8000` -> abre la asignatura **Panel de Métricas y BdC**.
- Puedes ver el resumen o pulsar en **Ver en página completa ->** para abrir el panel central a pantalla completa.

### 2. Pestaña superior en cualquier Asignatura (`extend_navigation_course`)
Gracias al gancho de navegación en `gitmetrics/lib.php`, el plugin inyecta una pestaña en la barra superior de navegación secundaria de cualquier curso de Moodle.
- **Cómo acceder**: Entra en cualquier asignatura -> en el menú superior de pestañas (*Curso | Configuración | Participantes | ...*) verás la pestaña **Métricas de Base de Conocimiento Git**. Al pulsarla, se abrirá el informe completo a pantalla completa para ese curso.

---

## Credenciales por defecto

| Servicio | URL | Usuario | Contraseña |
|---|---|---|---|
| Moodle | `http://localhost:8000` | `admin` | `adminpass123` |
| Element Web | `http://localhost:8081` | `admin` | `adminpass123` |
| MariaDB | `localhost:3306` (solo interno) | `bn_moodle` | `moodle_db_pass` |

---

## Documentación detallada

- **Plugin `gitmetrics`** → [`gitmetrics/README.md`](./gitmetrics/README.md)
  - Estructura del plugin, comandos de diagnóstico, métricas calculadas y opciones avanzadas
- **Entorno Docker** → [`moodle-matrix-dev/README.md`](./moodle-matrix-dev/README.md)
  - Configuración de Matrix, Ollama y servicios adicionales
