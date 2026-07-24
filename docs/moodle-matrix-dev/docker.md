# Configuración Docker Compose

Ubicación: `docker-compose.yml`

El archivo `docker-compose.yml` define el entorno de contenedores principal para `moodle-matrix-dev`. 

## Descripción de los Servicios

```yaml
--8<-- "moodle-matrix-dev/docker-compose.yml:file_desc"
```

### Componentes Principales:
- **mariadb**: Base de datos para Moodle.
- **moodle**: Aplicación principal de e-learning.
- **synapse**: Servidor Matrix local que permite la federación y mensajería en tiempo real.
- **element**: Cliente web ligero para conectarse a Matrix y visualizar los mensajes.
- **maubot**: Contenedor del framework de bots donde se aloja el plugin de GithubBot.
- **ollama**: Servicio opcional de LLM local si no se quiere depender de APIs externas (como Groq).

### Volúmenes de Persistencia
Los volúmenes `mariadb_data`, `moodle_data` y `moodledata_data` garantizan que la información no se pierda al reiniciar el entorno.
El volumen de Obsidian (`/obsidian-vault`) permite la lectura y exportación local de archivos si se configura una carpeta del host, de lo contrario apunta a `/tmp/okf-vault-placeholder`.
