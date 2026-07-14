# block_gitmetrics

Plugin de bloque para Moodle que analiza un repositorio Git (GitHub o GitLab) con estructura OKF y muestra metricas cuantitativas de la Base de Conocimiento.

Compatible con:
- **GitHub** (github.com)
- **GitLab OSL** (servidor GitLab de la Oficina de Software Libre de tu universidad)
- **GitLab local** (instancia GitLab corriendo en tu red o maquina)
- **GitLab cloud** (gitlab.com)

---

## Estructura del plugin

```
gitmetrics/
- block_gitmetrics.php          Clase principal del bloque
- version.php                   Version y compatibilidad
- settings.php                  Configuracion global (admin): proveedor, tokens, URL GitLab, TTL cache, rama
- edit_form.php                 Configuracion por instancia: proveedor, URL repo, rama, refresco
- renderer.php                  Renderizador HTML con CSS inline
- view.php                      Pagina de informe en pagina completa
- lib.php                       Hook de navegacion de cursos
- classes/
-   git_provider_interface.php  Interfaz comun para proveedores Git
-   github_client.php           Cliente HTTP para GitHub API (REST v3)
-   gitlab_client.php           Cliente HTTP para GitLab API (REST v4)
-   markdown_parser.php         Parser de frontmatter YAML, enlaces y validacion Markdown
-   metrics_calculator.php      Calculo de las 4 categorias de metricas
-   metrics_cache.php           Cache de resultados en BD Moodle con TTL
- cli/
-   setup_course.php            Script CLI para crear la asignatura Panel de Metricas
- db/
-   access.php                  Permisos/capabilities
-   install.xml                 Esquema de base de datos (tabla de cache)
-   upgrade.php                 Migraciones de version
- lang/
-   en/block_gitmetrics.php     Cadenas en ingles
-   es/block_gitmetrics.php     Cadenas en espanol (si existe)
```

---

## Requisitos

- Moodle 4.2 o superior (`requires = 2022041900`)
- Entorno Docker con `moodle-matrix-dev` levantado
- WSL con Docker instalado

---

## Instalacion rapida (un solo comando)

```bash
# Desde la carpeta del proyecto en WSL:
./instalar.sh
```

Al finalizar aparece:
```
 Moodle URL  : http://localhost:8000
 Usuario     : admin
 Contrasena  : adminpass123
```

---

## Eleccion del proveedor Git

El plugin soporta dos proveedores. Elige el que mejor se adapte a tu situacion:

| Proveedor | Cuando usarlo | URL de ejemplo |
| :--- | :--- | :--- |
| **GitHub** | Repositorio publico o privado en github.com | `https://github.com/owner/repo` |
| **GitLab OSL** | Servidor GitLab de tu universidad (OSL) | `https://gitlab.osl.ugr.es/grupo/repo` |
| **GitLab local** | GitLab en red interna o tu maquina | `http://localhost:8929/owner/repo` |
| **GitLab cloud** | Proyecto en gitlab.com | `https://gitlab.com/owner/repo` |

---

## Configuracion global (Administrador del sitio)

Accede a **Administracion del sitio > Plugins > Bloques > Git Knowledge Base Metrics**

### Paso 1 - Elegir proveedor por defecto

En el campo **"Default Git provider"** elige:
- `GitHub (github.com)` - para repositorios en GitHub
- `GitLab (OSL / local / gitlab.com)` - para cualquier instancia GitLab

### Paso 2 - Configurar GitHub (si usas GitHub)

1. Ve a tu perfil en GitHub > **Settings > Developer settings > Personal access tokens**.
2. Genera un token clasico con scope `repo` (o `public_repo` para repos publicos).
3. Pega el token en el campo **"GitHub API Token"**.

> Sin token: limite de 60 peticiones/hora por IP.
> Con token: limite de 5000 peticiones/hora.

### Paso 3 - Configurar GitLab (si usas GitLab OSL o local)

1. En el campo **"GitLab server URL"** escribe la URL base de tu servidor:
   - OSL universitaria: `https://gitlab.osl.ugr.es`
   - Local: `http://localhost:8929`
   - Cloud: `https://gitlab.com`
2. En **"GitLab Access Token (PRIVATE-TOKEN)"**:
   - Ve a tu instancia GitLab > **User Settings > Access Tokens**.
   - Crea un token con scope `read_api`.
   - Pega el token en el campo.

> Para repositorios publicos en GitLab el token es opcional.

---

## Configuracion por bloque (Profesor)

Cada instancia del bloque se puede configurar de forma independiente:

1. Activa la edicion en el curso (**Activar edicion** arriba a la derecha).
2. Haz clic en el engranaje/menu del bloque > **Configurar bloque**.
3. Rellena:
   - **Git provider** - elige GitHub o GitLab
   - **Repository URL** - la URL completa del repositorio:
     - GitHub: `https://github.com/usuario/repositorio`
     - GitLab OSL: `https://gitlab.osl.ugr.es/grupo/repositorio`
     - GitLab local: `http://localhost:8929/usuario/repositorio`
   - **Branch** - rama a analizar (por defecto: `main`)
4. Guarda.

---

## Opcion 1 - Asignatura dedicada "Panel de Metricas y BdC"

Al ejecutar `./instalar.sh` se crea automaticamente una asignatura **"Panel de Metricas y BdC"** con 4 secciones:

- **Volumen y Tamaño de la Base de Conocimiento**
- **Red de Enlaces e Interconectividad Markdown**
- **Taxonomia, Metadatos y Etiquetas YAML**
- **Calidad Markdown y Elementos Estructurales**

Para acceder:
1. Entra a `http://localhost:8000`
2. Inicia sesion con `admin` / `adminpass123`
3. En **"Mis cursos"** haz clic en **"Panel de Metricas y BdC"**

---

## Opcion 2 - Pestana superior en cualquier asignatura

Desde cualquier asignatura de Moodle:
1. En la barra de navegacion superior veras la pestana **"Metricas de Base de Conocimiento Git"**.
2. Haz clic para abrir la vista en pagina completa con los 4 acordeones de metricas.

---

## Diferencia entre Git, GitHub y GitLab

| Concepto | Que es | Donde corre |
| :--- | :--- | :--- |
| **Git** | Motor de control de versiones (hace los commits, ramas, historial) | En tu maquina local (consola) |
| **GitHub** | Plataforma en la nube para alojar repos Git. De Microsoft. | `github.com` (servidores externos) |
| **GitLab** | Plataforma DevOps completa para alojar repos Git. Puede auto-alojarse. | `gitlab.com` o en servidores propios |
| **GitLab OSL** | Instancia GitLab gestionada por la Oficina de Software Libre de la universidad. | Servidor interno de la universidad |

### Ventajas de usar el GitLab de la OSL

- **Soberania de datos**: el codigo y los contenidos no salen de los servidores de la universidad.
- **Sin limites de rate**: la API local no tiene limites de peticiones por hora.
- **Privacidad**: los proyectos academicos pueden ser privados sin depender de proveedores externos.
- **Integracion con el entorno universitario**: autenticacion con SSO/LDAP institucional.

---

## Arquitectura interna del cliente Git

```
metrics_calculator
       |
       +-- make_client(provider, token, gitlab_url)
              |
              +-- github_client   (implements git_provider_interface)
              |      API REST v3: api.github.com
              |      Raw: raw.githubusercontent.com
              |
              +-- gitlab_client   (implements git_provider_interface)
                     API REST v4: {gitlab_url}/api/v4/projects/{id}/repository/...
                     Paginacion automatica (100 items/pagina)
```

---

## Preguntas frecuentes

**¿Funciona con repositorios privados?**
Si. Configura el token correspondiente (GitHub PAT o GitLab PRIVATE-TOKEN) en los ajustes globales del plugin.

**¿Puedo cambiar de GitHub a GitLab sin reinstalar el plugin?**
Si. Simplemente cambia el proveedor en la configuracion global o por instancia de bloque.

**¿Que pasa si el servidor GitLab local no tiene certificado SSL valido?**
El plugin usa la clase `curl` de Moodle con `ignoresecurity => true` para permitir conexiones a servidores locales con certificados autofirmados.

**¿Funciona con namespaces anidados de GitLab (grupo/subgrupo/repo)?**
Si. El cliente GitLab extrae correctamente el namespace completo y el nombre del repositorio.
