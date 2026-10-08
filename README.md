# codex-llamacpp-proxy

Proxy compatible with the Responses API that connects Codex Desktop to llama.cpp's `llama-server`.

***Language***
* [🇪🇸 Español](README.es.md)
* 🇺🇸 English

## Background

The connection from Codex Desktop on Windows 11 to a local llama.cpp model was tested using the `profiles.local-llama` profile in `~/.codex/config.toml`. It was confirmed that `profile = "local-llama"` and `codex app -c ...` can connect Codex Desktop to local models.

However, connecting Codex Desktop directly to llama.cpp's OpenAI-compatible endpoint produced this error when starting a chat:

```json
{"error":{"code":400,"message":"'type' of tool must be 'function'","type":"invalid_request_error"}}
```

With `wire_api = "responses"`, Codex Desktop sends tools in the Responses API format. llama.cpp's OpenAI-compatible API expects tools in the Chat Completions format, such as `tools: [{"type":"function", ...}]`.

Disabling `web_search`, `image_generation`, and other features does not resolve the difference between the formats. Codex Desktop's configuration validation also rejects `wire_api = "chat"`.

## Purpose

`src/codex_llamacpp_proxy/proxy.py` provides a lightweight layer that adapts the two formats:

- Receives requests from Codex Desktop at `/v1/responses`.
- Converts and forwards them to llama.cpp's `/v1/chat/completions`.
- Wraps Responses API tools that are not `function` tools as Chat Completions `function` tools.
- Converts llama.cpp `tool_calls` into Responses API `function_call` items for Codex Desktop.

This allows regular conversations to work between Codex Desktop and a local llama.cpp model, without actually running external tools such as web search.

## Usage

With `llama-server` running at `http://127.0.0.1:8080/v1`, start the proxy:

```bash
uv run codex-llamacpp-proxy
```

To specify a different llama.cpp URL:

```bash
uv run codex-llamacpp-proxy --llama-base-url http://127.0.0.1:8080/v1
```

To enable debug logging:

```bash
PROXY_DEBUG=1 uv run codex-llamacpp-proxy
```

Stop the process with Ctrl-C.

## Codex configuration: `~/.codex/config.toml`

When using the `local-llama` profile with the Codex Desktop app, uncomment this line. Comment it again to return to the OpenAI cloud API. Codex CLI does not require this change.

```toml
# profile="local-llama"
```

Configure the profile, for example:

```toml
[profiles.local-llama]
model_provider = "llamacpp-local"
model = "qwen3.6-35b-a3b"
model_context_window = 262144
model_auto_compact_token_limit = 240000
```

Set `base_url` to the proxy instead of connecting directly to llama.cpp:

```toml
[model_providers.llamacpp-local]
name = "llama.cpp via local responses proxy"
base_url = "http://127.0.0.1:8090/v1"
wire_api = "responses"
requires_openai_auth = false
```

Start Codex CLI with the profile:

```bash
codex --profile local-llama
```

You can launch Codex Desktop from a terminal, shortcut, or launcher application. When configured correctly, the label that usually shows something like `5.5` should show the value of `model_providers.llamacpp-local.name` instead (in this example, `llama.cpp via local responses proxy`).

## Current limitations

This proxy is an experimental conversion layer for forwarding requests to llama.cpp. It does not run all of Codex Desktop's built-in tools.

For example, `web_search` and `image_generation` are converted into `function` tools that llama.cpp can receive, but the proxy does not perform searches or generate images. Its primary goal is to support regular conversations.

## Implementation notes

Testing found cases where a direct format conversion did not let the Codex Desktop turn finish correctly. `src/codex_llamacpp_proxy/proxy.py` includes the following compatibility adjustments.

### Closing SSE connections

Codex Desktop could remain in the `Working...` state even after receiving the response text. One possible cause was that, although the SSE response sent `response.completed` and `[DONE]`, the HTTP connection remained open and Codex Desktop did not detect the end of the stream.

For that reason, Responses API SSE replies include `Connection: close` and set `handler.close_connection = True`.

### Avoiding assistant prefill

With some Qwen models, llama.cpp could return this error:

```json
{"error":{"code":400,"message":"Assistant response prefill is incompatible with enable_thinking.","type":"invalid_request_error"}}
```

Codex Desktop Responses API requests may include previous assistant replies in the history. Converting them directly into Chat Completions `messages` can cause the final `assistant` message to be interpreted as assistant prefill by the llama.cpp/Qwen chat template, conflicting with `enable_thinking`.

Before forwarding the request to Chat Completions, `strip_assistant_prefill()` removes trailing `assistant` messages to avoid this conflict.

### Converting usage formats

Codex Desktop may also report a parsing error like this:

```text
stream disconnected before completion: failed to parse ResponseCompleted: missing field `input_tokens`
```

llama.cpp Chat Completions usage has `prompt_tokens`, `completion_tokens`, and `total_tokens`. The Responses API expects `input_tokens`, `output_tokens`, and `total_tokens`.

`responses_usage_from_chat_usage()` converts the `usage` object included in `response.completed` to the Responses API format. If llama.cpp does not return usage data, zero values are sent so Codex Desktop can parse the response.

## Credits

This project is based on the original repository by [sasasin/codex-llamacpp-proxy](https://github.com/sasasin/codex-llamacpp-proxy).
