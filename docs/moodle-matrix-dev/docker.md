# Configuración Docker Compose

Ubicación: `docker-compose.yml`

El archivo `docker-compose.yml` define el entorno de contenedores principal para `moodle-matrix-dev`. 

## Descripción de los Servicios

```yaml
```python
services:
  mariadb:
    image: mariadb:10.11
    container_name: moodle-mariadb
    environment:
      - MARIADB_USER=bn_moodle
      - MARIADB_PASSWORD=moodle_db_pass
      - MARIADB_DATABASE=bitnami_moodle
      - MARIADB_ROOT_PASSWORD=moodle_root_pass
    volumes:
      - mariadb_data:/var/lib/mysql

  moodle:
    image: bitnamilegacy/moodle:latest
    container_name: moodle-app
    ports:
      - "8000:8080"
    environment:
      - MOODLE_DATABASE_HOST=mariadb
      - MOODLE_DATABASE_PORT_NUMBER=3306
      - MOODLE_DATABASE_USER=bn_moodle
      - MOODLE_DATABASE_PASSWORD=moodle_db_pass
      - MOODLE_DATABASE_NAME=bitnami_moodle
      - MOODLE_USERNAME=admin
      - MOODLE_PASSWORD=adminpass123
      - MOODLE_EMAIL=admin@example.com
      - MOODLE_SITE_NAME=Moodle Matrix Dev
      - MOODLE_HOST=localhost:8000
    depends_on:
      - mariadb
    volumes:
      - moodle_data:/bitnami/moodle
      - moodledata_data:/bitnami/moodledata
      - ${OBSIDIAN_VAULT_PATH:-/tmp/okf-vault-placeholder}:/obsidian-vault

  synapse:
    image: matrixdotorg/synapse:latest
    container_name: matrix-synapse
    restart: unless-stopped
    ports:
      - "8008:8008"
    volumes:
      - ./synapse-data:/data

  element:
    image: vectorim/element-web:latest
    container_name: element-web
    ports:
      - "8081:80"
    volumes:
      - ./element-config.json:/app/config.json:ro
      - ./default.conf.template:/etc/nginx/templates/default.conf.template:ro
    depends_on:
      - synapse

  maubot:
    build:
      context: ./maubot
      dockerfile: Dockerfile.maubot
    container_name: maubot
    restart: unless-stopped
    volumes:
      - ./maubot/maubot-data:/data
      - ./maubot/llm-wiki-assistant-plugin:/plugin-src:ro
    ports:
      - "29316:29316"
    depends_on:
      - synapse

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    volumes:
      - ./ollama-data:/root/.ollama
    ports:
      - "11434:11434"

volumes:
  mariadb_data:
    driver: local
  moodle_data:
    driver: local
  moodledata_data:
    driver: local
```


### Componentes Principales:
- **mariadb**: Base de datos para Moodle.
- **moodle**: Aplicación principal de e-learning.
- **synapse**: Servidor Matrix local que permite la federación y mensajería en tiempo real.
- **element**: Cliente web ligero para conectarse a Matrix y visualizar los mensajes.
- **maubot**: Contenedor del framework de bots donde se aloja el plugin de LlmWikiAssistant.
- **ollama**: Servicio opcional de LLM local si no se quiere depender de APIs externas (como Groq).

### Volúmenes de Persistencia
Los volúmenes `mariadb_data`, `moodle_data` y `moodledata_data` garantizan que la información no se pierda al reiniciar el entorno.
El volumen de Obsidian (`/obsidian-vault`) permite la lectura y exportación local de archivos si se configura una carpeta del host, de lo contrario apunta a `/tmp/okf-vault-placeholder`.
