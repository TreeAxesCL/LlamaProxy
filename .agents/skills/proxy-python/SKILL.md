---
name: proxy-python
description: Modify or review this project's Python proxy behavior, including HTTP routes, Responses and Chat Completions conversion, SSE, tool format conversion, or llama.cpp transport.
---

# Cambios Python del proxy

Usa esta skill cuando una tarea cambie el comportamiento o la estructura del proxy Python.

## Responsabilidades

- Rutas y ciclo de vida HTTP: `src/codex_llamacpp_proxy/server.py`.
- Conversiones de mensajes y respuestas, incluidas respuestas SSE: `conversion.py`.
- Transformación actual de definiciones `tools` y `tool_choice`: `tools.py`.
- Solicitudes HTTP upstream: `upstream.py`.
- Helpers compartidos y logging: `utils.py`.
- Configuración y argumentos: `config.py`.

Sigue la ruta real de la solicitud y modifica el módulo que posee esa responsabilidad. Mantén los módulos pequeños y evita capas nuevas si una función del módulo actual basta.

## Invariantes

- Conserva las rutas HTTP y los formatos existentes, incluido el encuadre SSE y `usage`, salvo que el usuario pida cambiarlos.
- El proxy adapta formatos; no ejecuta herramientas externas.
- No implementes compatibilidad especial para namespace, MCP, web search ni workarounds de Codex/llama.cpp a menos que el usuario lo solicite expresamente.
- Reutiliza la biblioteca estándar y no añadas dependencias sin necesidad concreta.
- Conserva o reemplaza cada prueba existente por una que verifique el mismo comportamiento; no borres cobertura solo porque el código se haya movido.

Al modificar Python, sigue los comandos de lint, formato y pytest definidos en `AGENTS.md`.
