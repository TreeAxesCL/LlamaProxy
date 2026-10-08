# Instrucciones para agentes de IA

Estas instrucciones aplican a cualquier agente que trabaje en este repositorio. Sigue también las instrucciones específicas del usuario para cada tarea.

## Mapa del proyecto

- `src/codex_llamacpp_proxy/config.py`: defaults, lectura TOML, entorno, CLI y validación.
- `src/codex_llamacpp_proxy/server.py`: rutas HTTP y arranque del servidor.
- `src/codex_llamacpp_proxy/conversion.py`: conversión Responses API ↔ Chat Completions, incluidas respuestas SSE.
- `src/codex_llamacpp_proxy/tools.py`: conversión actual de definiciones y elecciones de herramientas.
- `src/codex_llamacpp_proxy/upstream.py`: transporte HTTP hacia llama.cpp.
- `src/codex_llamacpp_proxy/utils.py`: helpers JSON/SSE, identificadores y logging compartidos.
- `src/codex_llamacpp_proxy/proxy.py`: fachada de compatibilidad para imports antiguos.
- `src/codex_llamacpp_proxy/__main__.py`: entrada `python -m codex_llamacpp_proxy`.
- `tests/`: pruebas de configuración, conversiones, streaming, transporte y endpoints.
- `README.es.md` y `config.toml.example`: documentación y configuración de referencia.

## Reglas de implementación

- Mantén Python explícito y pequeño. Prefiere la biblioteca estándar; no agregues dependencias o abstracciones sin necesidad concreta.
- Conserva las rutas `/health`, `/v1/health`, `/v1/models`, `/v1/chat/completions` y `/v1/responses`, así como los formatos actuales de respuestas, SSE y `usage`.
- Mantén el default de llama.cpp centralizado en `config.py`. La precedencia es CLI > entorno > TOML > defaults; actualiza pruebas y documentación si cambia el esquema.
- Usa `tomllib` para TOML. El proyecto requiere Python 3.11 o posterior.
- Modifica el módulo responsable y prueba el contrato observable. Conserva los tests existentes; no los elimines para facilitar una refactorización.
- Mantén `README.es.md` en español y sincroniza `config.toml.example` cuando cambie la configuración.
- No añadas soporte especial de Codex, namespace, MCP, web search, ejecución de herramientas externas ni workarounds Codex/llama.cpp salvo que el usuario lo solicite expresamente. No modifiques Codex ni llama.cpp.

## Verificación Python

Después de modificar código Python, ejecuta y confirma estos comandos:

```bash
uv run --group dev ruff check . --fix
uv run --group dev ruff format .
uv run --group dev pytest --cov-report=xml --cov-report=html
```

Si permisos o caché impiden ejecutar un comando, vuelve a intentarlo solicitando la aprobación necesaria; no omitas la verificación.

## Skills del repositorio

- `.agents/skills/proxy-python/SKILL.md`: cambios de servidor, conversiones, herramientas y transporte.
- `.agents/skills/proxy-config/SKILL.md`: cambios en configuración TOML, entorno o CLI.
