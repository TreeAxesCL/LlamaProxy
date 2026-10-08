# LlamaProxy for Codex

Small HTTP proxy that receives Chat Completions and Responses API requests and forwards them to the API supported by `llama-server`. It preserves the current routes and conversions, including SSE streaming and function calling.

## Language

- 🇪🇸 [Español](README.es.md)
- 🇺🇸 English

## Architecture

```text
Responses API compatible client
             ↓
       local HTTP server
             ↓
   conversion / transport
             ↓
       llama-server
```

The current tool conversion only adapts formats. The proxy does not execute external tools.

## Project structure

```text
src/codex_llamacpp_proxy/
├── __main__.py       # python -m codex_llamacpp_proxy
├── config.py         # defaults, TOML, environment, CLI, and validation
├── conversion.py     # messages, responses, and Responses SSE events
├── server.py         # HTTP routes and startup
├── tools.py          # existing tool definition conversion
├── upstream.py       # HTTP requests to llama.cpp
├── utils.py          # JSON, SSE, IDs, and logging
└── proxy.py          # compatibility imports for older code
tests/
├── test_config.py
├── test_import.py
└── test_proxy.py
```

## Installation

Python 3.11 or later is required. For development, install [uv](https://docs.astral.sh/uv/) and the dependencies in the `dev` group:

```bash
uv sync --group dev
```

TOML is read with `tomllib` from the Python standard library; no TOML dependency is needed.

## Run

With the defaults, the proxy listens on `127.0.0.1:8090` and forwards requests to `http://127.0.0.1:8000/v1`:

```bash
python -m codex_llamacpp_proxy
```

Override the main options from the CLI:

```bash
python -m codex_llamacpp_proxy --host 127.0.0.1 --port 8090
python -m codex_llamacpp_proxy --port 8090
python -m codex_llamacpp_proxy --llama-base-url http://127.0.0.1:8000/v1
python -m codex_llamacpp_proxy --model local-model --debug
```

Point the client's Responses API base URL to the proxy, for example `http://127.0.0.1:8090/v1`.

## TOML configuration

Copy `config.toml.example` to `config.toml` and edit the values:

```toml
[server]
host = "127.0.0.1"
port = 8090

[llama]
base_url = "http://127.0.0.1:8000/v1"
model = "local-model"

[proxy]
debug = false
```

Pass the file at startup:

```bash
python -m codex_llamacpp_proxy --config config.toml
```

Without `--config`, the proxy uses defaults; it does not search for or create a config file automatically. A specified file that is missing or contains invalid TOML produces an error.

## Environment variables and precedence

| Option | Environment variable | Default |
| --- | --- | --- |
| Host | `PROXY_HOST` | `127.0.0.1` |
| Port | `PROXY_PORT` | `8090` |
| llama.cpp base URL | `LLAMA_CPP_BASE_URL` | `http://127.0.0.1:8000/v1` |
| Fallback model | `LLAMA_CPP_MODEL` | empty |
| Debug logging | `PROXY_DEBUG` | `false` |

Each setting follows **CLI > environment > TOML > defaults** precedence. For example, `LLAMA_CPP_BASE_URL` overrides `[llama].base_url`, and `--llama-base-url` overrides both. `PROXY_DEBUG` accepts `1`, `true`, `yes`, and `on` as true. The `--debug` option enables debug logging.

The port must be between 1 and 65535. The llama.cpp URL must be an absolute HTTP or HTTPS URL. Trailing slashes are normalized.

## Available routes

- `GET /health` and `GET /v1/health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`

## Tests and code quality

```bash
uv run --group dev pytest
uv run --group dev ruff check .
uv run --group dev ruff format --check .
```

## Out of scope

The existing tool conversion is in `tools.py`; generic Responses API tool wrappers remain unchanged. The proxy does not execute tools, implement MCP, namespace support, or web search. Responses API message conversion is in `conversion.py`, and llama.cpp transport is in `upstream.py`; these are the extension points for future work.

## Credits

This project is based on the original [codex-llamacpp-proxy](https://github.com/sasasin/codex-llamacpp-proxy). Thanks to its author and contributors for their work.
