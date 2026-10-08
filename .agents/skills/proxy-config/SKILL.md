---
name: proxy-config
description: Add or change configuration for this project, including TOML keys, environment variables, CLI options, defaults, validation, or config documentation.
---

# Configuración del proxy

Usa esta skill para tareas que cambien cómo se configura el proxy.

## Fuente de verdad

`src/codex_llamacpp_proxy/config.py` define `Config`, los defaults y la resolución de valores. Mantén el orden **CLI > entorno > TOML > defaults**. Python 3.11+ incluye `tomllib`; no agregues una dependencia para leer TOML.

El ejemplo público está en `config.toml.example`. La guía en español está en `README.es.md`. El archivo `config.toml` es la configuración activa del repositorio y debe corresponder al ejemplo salvo que el usuario pida valores distintos.

## Al cambiar opciones

- Mantén cada default en un único lugar dentro de `config.py`.
- Valida valores externos y devuelve errores de configuración claros.
- Prueba defaults, TOML, entorno, CLI, precedencia, ausencia del archivo, valores inválidos y normalización de URL aplicable al cambio.
- Actualiza el ejemplo y la documentación junto con el código.
- No leas ni escribas configuración fuera del repositorio como efecto secundario.

Al modificar Python, sigue los comandos de lint, formato y pytest definidos en `AGENTS.md`.
