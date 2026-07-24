# Empaquetado y Configuración (Maubot)

Ubicación: `github-bot-plugin/`

La integración del LLM y de Git con la sala de Matrix se realiza mediante un bot construido sobre la plataforma **Maubot**. 

## Dockerfile y Despliegue

La imagen personalizada se construye sobre la base de Alpine y se encarga de instalar dependencias críticas de cifrado (`olm-dev`, `maubot[encryption]`) y utilidades como `zip` necesarias para construir el `.mbp` (Maubot Plugin Bundle).

```dockerfile
--8<-- "moodle-matrix-dev/github-bot-plugin/Dockerfile.maubot:file_desc"
```

## `entrypoint.sh`

El punto de entrada del contenedor compila dinámicamente el código fuente alojado en la carpeta de desarrollo al arrancar, generando un archivo ZIP (`.mbp`) sin necesidad de realizar compilaciones manuales.

```bash
--8<-- "moodle-matrix-dev/github-bot-plugin/entrypoint.sh:file_desc"
```

## Configuración Base del Plugin

La configuración base permite indicar los credenciales de Git, la URL del LLM y los distintos modelos utilizados.

```yaml
--8<-- "moodle-matrix-dev/github-bot-plugin/github-bot-plugin/base-config.yaml.example:file_desc"
```
