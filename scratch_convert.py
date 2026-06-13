import os

filepath = os.path.join("frontend", "src", "App.jsx")

with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

# Substitui todos os fetch por apiFetch
code = code.replace("fetch(", "apiFetch(")

# Restaura o fetch nativo dentro do próprio helper apiFetch
code = code.replace(
    "return apiFetch(`${apiBase}${url}`, options);",
    "return fetch(`${apiBase}${url}`, options);"
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)

print("Substituição concluída com sucesso!")
