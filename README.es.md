# codex-llamacpp-proxy

Proxy compatible con Responses API que conecta Codex Desktop con `llama-server` de llama.cpp.

***Idioma***
* 🇪🇸 Español
* [🇺🇸 English](README.md)

## Contexto

Se probó la conexión de Codex Desktop en Windows 11 con un modelo local de llama.cpp mediante el perfil `profiles.local-llama` de `~/.codex/config.toml`. Se confirmó que `profile = "local-llama"` y `codex app -c ...` permiten conectar Codex Desktop con modelos locales.

Sin embargo, al conectar Codex Desktop directamente con el endpoint compatible con OpenAI de llama.cpp, al iniciar un chat aparecía este error:

```json
{"error":{"code":400,"message":"'type' of tool must be 'function'","type":"invalid_request_error"}}
```

Codex Desktop, con `wire_api = "responses"`, envía herramientas en formato Responses API. La API compatible con OpenAI de llama.cpp espera herramientas en formato Chat Completions, como `tools: [{"type":"function", ...}]`.

Desactivar `web_search`, `image_generation` y otras funciones no resuelve la diferencia entre ambos formatos. Además, la validación de configuración de Codex Desktop rechaza `wire_api = "chat"`.

## Propósito

`src/codex_llamacpp_proxy/proxy.py` implementa una capa ligera que adapta ambos formatos:

- Recibe solicitudes de Codex Desktop en `/v1/responses`.
- Las convierte y las reenvía a `/v1/chat/completions` de llama.cpp.
- Envuelve las herramientas Responses API que no sean `function` como herramientas `function` de Chat Completions.
- Convierte los `tool_calls` de llama.cpp en elementos `function_call` de Responses API para Codex Desktop.

Así, las conversaciones normales —sin ejecutar realmente herramientas externas como la búsqueda web— pueden funcionar desde Codex Desktop con un modelo local de llama.cpp.

## Uso

Con `llama-server` ejecutándose en `http://127.0.0.1:8080/v1`, inicia el proxy:

```bash
uv run codex-llamacpp-proxy
```

Para indicar otra URL de llama.cpp:

```bash
uv run codex-llamacpp-proxy --llama-base-url http://127.0.0.1:8080/v1
```

Para activar los registros de depuración:

```bash
PROXY_DEBUG=1 uv run codex-llamacpp-proxy
```

Detén el proceso con Ctrl-C.

## Configuración de Codex: `~/.codex/config.toml`

Al usar el perfil `local-llama` con la aplicación Codex Desktop, descomenta la línea siguiente. Vuelve a comentarla para regresar a la API en la nube de OpenAI. En Codex CLI no es necesario cambiarla.

```toml
# profile="local-llama"
```

Configura el perfil, por ejemplo, así:

```toml
[profiles.local-llama]
model_provider = "llamacpp-local"
model = "qwen3.6-35b-a3b"
model_context_window = 262144
model_auto_compact_token_limit = 240000
```

En `base_url`, apunta al proxy en vez de conectar directamente con llama.cpp:

```toml
[model_providers.llamacpp-local]
name = "llama.cpp via local responses proxy"
base_url = "http://127.0.0.1:8090/v1"
wire_api = "responses"
requires_openai_auth = false
```

Inicia Codex CLI con el perfil:

```bash
codex --profile local-llama
```

Puedes iniciar Codex Desktop desde una terminal, un acceso directo o una aplicación lanzadora. Si la configuración es correcta, el nombre que aparece donde normalmente se muestra, por ejemplo, `5.5` será el valor de `model_providers.llamacpp-local.name` (en este ejemplo, `llama.cpp via local responses proxy`).

## Limitaciones actuales

Este proxy es una capa experimental de conversión para enviar solicitudes a llama.cpp. No ejecuta todas las herramientas integradas de Codex Desktop.

Por ejemplo, `web_search` e `image_generation` se convierten al formato de herramientas `function` que llama.cpp puede recibir, pero el proxy no realiza búsquedas ni genera imágenes. El objetivo principal es permitir conversaciones normales.

## Notas de implementación

Durante las pruebas se detectaron casos en los que una conversión directa no permitía que el turno de Codex Desktop terminara correctamente. `src/codex_llamacpp_proxy/proxy.py` incluye estas adaptaciones de compatibilidad.

### Cierre de SSE

Aunque ya se hubiera recibido el texto de la respuesta, Codex Desktop podía quedarse en estado `Working...`. Una posible causa era que, pese a enviar `response.completed` y `[DONE]` en la respuesta SSE, la conexión HTTP no se cerraba y Codex Desktop no detectaba el fin del flujo.

Por eso, las respuestas SSE de Responses API incluyen `Connection: close` y establecen `handler.close_connection = True`.

### Evitar el prefill del asistente

Con algunos modelos Qwen, llama.cpp podía devolver este error:

```json
{"error":{"code":400,"message":"Assistant response prefill is incompatible with enable_thinking.","type":"invalid_request_error"}}
```

Las solicitudes Responses API de Codex Desktop pueden incluir respuestas anteriores del asistente en el historial. Al convertirlas directamente a `messages` de Chat Completions, el último mensaje `assistant` puede interpretarse como un prefill del asistente en la plantilla de chat de llama.cpp/Qwen y entrar en conflicto con `enable_thinking`.

Antes de reenviar la solicitud a Chat Completions, `strip_assistant_prefill()` elimina los mensajes `assistant` finales para evitar ese conflicto.

### Conversión del formato de uso

Codex Desktop también puede mostrar un error de análisis como este:

```text
stream disconnected before completion: failed to parse ResponseCompleted: missing field `input_tokens`
```

El uso de tokens de Chat Completions en llama.cpp utiliza `prompt_tokens`, `completion_tokens` y `total_tokens`. Responses API espera `input_tokens`, `output_tokens` y `total_tokens`.

`responses_usage_from_chat_usage()` convierte el objeto `usage` incluido en `response.completed` al formato Responses API. Si llama.cpp no devuelve datos de uso, se envían valores en cero para que Codex Desktop pueda analizar la respuesta.

## Créditos

Este proyecto se basa en el repositorio original de [sasasin/codex-llamacpp-proxy](https://github.com/sasasin/codex-llamacpp-proxy).
