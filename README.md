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
- Acceso a `http://localhost:8000` (Moodle), `http://localhost:8008` (Synapse), `http://localhost:8081` (Element)

---

## Inicio rápido

```bash
# 1. Situarse en el directorio del proyecto
cd /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas

# 2. Levantar el entorno Docker
cd moodle-matrix-dev
docker compose up -d

# Esperar hasta ver: "** Moodle setup finished! **"
docker compose logs -f moodle

# 3. Instalar el plugin de Moodle
docker cp \
  /mnt/c/Users/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/gitmetrics \
  moodle-app:/bitnami/moodle/blocks/gitmetrics

docker exec --user root moodle-app \
  chown -R daemon:daemon /bitnami/moodle/blocks/gitmetrics

# 4. Activar el plugin en Moodle
# Abre http://localhost:8000/admin/index.php → "Actualizar base de datos de Moodle ahora"
```

---

## Credenciales por defecto

| Servicio | URL | Usuario | Contraseña |
|---|---|---|---|
| Moodle | `http://localhost:8000` | `adminmoodle` | `test1234` |
| Element Web | `http://localhost:8081` | `admin` | `adminpass123` |
| MariaDB | `localhost:3306` (solo interno) | `bn_moodle` | `moodle_db_pass` |

---

## Documentación detallada

- **Plugin `gitmetrics`** → [`gitmetrics/README.md`](./gitmetrics/README.md)
  - Estructura del plugin, instalación paso a paso, comandos de diagnóstico y métricas calculadas
- **Entorno Docker** → [`moodle-matrix-dev/README.md`](./moodle-matrix-dev/README.md)
  - Configuración de Moodle + Matrix, Ollama y servicios adicionales
