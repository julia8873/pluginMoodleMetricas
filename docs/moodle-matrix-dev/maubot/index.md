# Empaquetado y Configuración (Maubot)

Ubicación: `maubot/`

La integración del LLM y de Git con la sala de Matrix se realiza mediante un bot construido sobre la plataforma Maubot. 

## Dockerfile y Despliegue

El `Dockerfile.maubot` realiza los siguientes pasos para construir la imagen:

1. **Partir de la imagen base**: Usa `dock.mau.dev/maubot/maubot:latest` como punto de partida.
2. **Añadir el repositorio community de Alpine**: Necesario para instalar ciertas dependencias adicionales del sistema que no vienen por defecto.
3. **Instalar dependencias del sistema**: Se instalan `olm-dev`, `build-base` y `zip`, requeridos para el cifrado y para construir el empaquetado del plugin.
4. **Instalar dependencias de Python del plugin**: Instala `pypdf`, `pymupdf` (para procesamiento de documentos) y la extensión `maubot[encryption]` (cifrado extremo a extremo) a través de `pip`.
5. **Copiar el código fuente**: Traspasa el directorio del plugin (`llm-wiki-assistant-plugin/`) hacia el directorio `/plugin-src/` dentro de la imagen.
6. **Configurar el script de arranque**: Copia `entrypoint.sh`, le otorga permisos de ejecución y lo define como el punto de entrada (`ENTRYPOINT`). Este script empaquetará el código antes de arrancar maubot.


```dockerfile
--8<-- "moodle-matrix-dev/maubot/Dockerfile.maubot:file_desc"
```

## `entrypoint.sh`

El punto de entrada del contenedor compila dinámicamente el código fuente alojado en la carpeta de desarrollo al arrancar, generando un archivo ZIP (`.mbp`) sin necesidad de realizar compilaciones manuales.

El script `entrypoint.sh` realiza los siguientes pasos para preparar e iniciar el bot:

1. **Definir variables clave**: Establece los directorios de trabajo y el identificador del plugin.
2. **Extraer la versión**: Lee la versión desde `maubot.yaml` para nombrar el archivo correctamente.
3. **Limpiar el entorno**: Elimina empaquetados `.mbp` anteriores del plugin en el destino para evitar duplicados.
4. **Preparar archivos**: Copia el código fuente y las configuraciones (`maubot.yaml`, `base-config.yaml`) a un directorio temporal, ignorando la caché de python.
5. **Empaquetar**: Comprime todo el contenido del directorio temporal en un formato ZIP y lo ubica en `/data/plugins` (directorio que lee Maubot).
6. **Arrancar el servidor**: Ejecuta la instancia principal de Maubot pasándole el archivo de configuración.

```bash
--8<-- "moodle-matrix-dev/maubot/entrypoint.sh:file_desc"
```


## Configuración Base del Plugin

La configuración base (`base-config.yaml`) permite indicar las credenciales de Git, la URL del LLM y los distintos modelos utilizados. Definiendo los siguientes puntos:

1. **Conexión a Git**: Se especifica el proveedor (ej. `gitlab`), la URL, el token de acceso, el propietario, el repositorio por defecto y la rama principal (`main`) para la sincronización con la Base de Conocimiento (BdC).
2. **Directorio Raw**: Define que las subidas en bruto sin procesar irán a la carpeta `raw/`.
3. **LLM Principal**: Establece el modelo de lenguaje principal para procesar interacciones, su URL de API base y la llave de autorización (API key).
4. **LLM de Visión (Opcional)**: Permite configurar un segundo modelo estrictamente para la extracción multimodal de texto en imágenes y documentos escaneados. Si se omite, se usa el principal.
5. **Caché (TTL)**: Configura el tiempo de vida en minutos (`bdc_cache_ttl_minutos`) del árbol de archivos en caché, lo cual evita recargas innecesarias desde Git durante una sesión.
6. **Ingesta Automática**: El parámetro `ingest_automatico` permite activar o desactivar que las nuevas subidas a `raw/` sean re-organizadas de inmediato usando el LLM para generar conceptos bajo la estructura de conocimiento de la BdC.

```yaml
--8<-- "moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/base-config.yaml.example:file_desc"
```

