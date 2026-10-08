# Instrucciones para Codex

## Estructura del proyecto

- `src/codex_llamacpp_proxy/proxy.py` contiene el servidor HTTP y las conversiones entre Responses API y Chat Completions.
- `src/codex_llamacpp_proxy/__main__.py` permite iniciar el programa como módulo.
- `tests/` contiene las pruebas de conversión, streaming y endpoints.
- `README.md` es la guía de uso en español.

## Cambios

- Mantén la implementación pequeña y usa la biblioteca estándar; no agregues dependencias sin necesidad concreta.
- Conserva la compatibilidad entre Responses API y Chat Completions, incluidos los formatos SSE y `usage` que consume Codex.
- Añade o ajusta pruebas en `tests/` cuando cambies el comportamiento de Python.
- Mantén el README en español y actualiza los ejemplos si cambian los comandos, opciones o configuración.

## Verificación de cambios Python

Al modificar código Python, ejecuta estos comandos y confirma que todos terminen correctamente:

```bash
uv run --group dev ruff check . --fix
uv run --group dev ruff format .
uv run --group dev pytest --cov-report=xml --cov-report=html
```

Si algún comando no puede completarse en el sandbox por permisos o acceso a la caché, vuelve a ejecutarlo solicitando la aprobación necesaria; no lo omitas.
