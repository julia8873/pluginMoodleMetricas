import os
import glob
import re

mixin_dir = "/home/julia/Desktop/PracticasCEPRUD/pluginMoodleMetricas/moodle-matrix-dev/maubot/llm-wiki-assistant-plugin/llm_wiki_assistant/mixins"
files = glob.glob(mixin_dir + "/**/*.py", recursive=True)

for file in files:
    with open(file, "r") as f:
        content = f.read()

    # Pattern 1: owner, repo, token = self.config["default_owner"], self.config["default_repo"], self._obtener_git_token()
    content = re.sub(
        r'owner, repo, token = self\.config\["default_owner"\], self\.config\["default_repo"\], self\._obtener_git_token\(\)\n*',
        '', content
    )
    # Pattern 2: owner = self.config["default_owner"] \n repo = self.config["default_repo"] \n token = self._obtener_git_token()
    content = re.sub(r'owner = self\.config\["default_owner"\]\n\s*repo = self\.config\["default_repo"\]\n\s*token = self\._obtener_git_token\(\)\n*', '', content)
    content = re.sub(r'owner = self\.config\["default_owner"\]\n\s*repo = self\.config\["default_repo"\]\n*', '', content)

    # Reemplazar llamadas a métodos refactorizados en GitMixin
    content = re.sub(r'self\._obtener_documentacion\(\s*owner,\s*repo,\s*token,?', r'self._obtener_documentacion(evt.sender,', content)
    content = re.sub(r'self\._obtener_documentacion\(\s*owner,\s*repo,\s*token\s*\)', r'self._obtener_documentacion(evt.sender)', content)
    content = re.sub(r'self\._obtener_agents_md\(\s*owner,\s*repo,\s*token\s*\)', r'self._obtener_agents_md(evt.sender)', content)
    content = re.sub(r'self\._listar_carpetas\(\s*owner,\s*repo,\s*token\s*\)', r'self._listar_carpetas(evt.sender)', content)
    content = re.sub(r'self\._recorrer_carpeta\(\s*session,\s*owner,\s*repo,\s*headers,\s*path', r'self._recorrer_carpeta(session, evt.sender, path', content)
    content = re.sub(r'self\._listar_rutas\(\s*session,\s*owner,\s*repo,\s*headers,\s*""\s*\)', r'self._listar_rutas(session, evt.sender, "")', content)
    content = re.sub(r'self\._listar_rutas\(\s*session,\s*owner,\s*repo,\s*headers,\s*([^)]+)\)', r'self._listar_rutas(session, evt.sender, \1)', content)
    content = re.sub(r'self\._recorrer_carpeta_con_sha\(\s*session,\s*owner,\s*repo,\s*headers,\s*([^)]+)\)', r'self._recorrer_carpeta_con_sha(session, evt.sender, \1)', content)
    content = re.sub(r'self\._obtener_sha_y_contenido_github\(\s*session,\s*owner,\s*repo,\s*headers,\s*([^)]+)\)', r'self._obtener_sha_y_contenido_github(session, evt.sender, \1)', content)
    
    # upload/delete/move
    content = re.sub(r'self\._borrar_archivo_github\(\s*owner,\s*repo,\s*token,\s*([^,]+),\s*branch,?', r'self._borrar_archivo_github(evt.sender, \1,', content)
    content = re.sub(r'self\._mover_archivo_github\(\s*owner,\s*repo,\s*token,\s*([^,]+),\s*([^,]+),\s*branch,\s*evt\.sender\s*\)', r'self._mover_archivo_github(evt.sender, \1, \2)', content)
    content = re.sub(r'self\._subir_o_actualizar_archivo_github\(\s*owner,\s*repo,\s*token,\s*([^,]+),\s*([^,]+),\s*branch,?', r'self._subir_o_actualizar_archivo_github(evt.sender, \1, \2,', content)
    content = re.sub(r'self\._append_log_okf\(\s*owner,\s*repo,\s*token,\s*branch,?', r'self._append_log_okf(evt.sender,', content)
    content = re.sub(r'self\._resolver_ruta_unica\(\s*evt,\s*([^,]+),\s*owner,\s*repo,\s*headers\s*\)', r'self._resolver_ruta_unica(evt, \1)', content)
    
    # default_branch replacement to get it from context if needed, but actually branch was used as self.config["default_branch"]
    # We should let the user script handle branch locally. Let's not remove default_branch unless it's unused.

    with open(file, "w") as f:
        f.write(content)
