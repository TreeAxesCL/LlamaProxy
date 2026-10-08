# codex-llamacpp-proxy

Proxy HTTP pequeño que recibe solicitudes de Chat Completions y Responses API, y las reenvía a la API compatible de `llama-server`. Conserva las rutas y conversiones actuales del proyecto, incluido el streaming SSE y function calling.

## Arquitectura

```text
Cliente compatible con Responses API
             ↓
      servidor HTTP local
             ↓
 conversión / transporte
             ↓
      llama-server
```

La conversión actual de herramientas solo adapta los formatos. El proxy no ejecuta herramientas externas.

## Estructura

```text
src/codex_llamacpp_proxy/
├── __main__.py       # python -m codex_llamacpp_proxy
├── config.py         # defaults, TOML, entorno, CLI y validación
├── conversion.py     # mensajes, respuestas y eventos Responses SSE
├── server.py         # rutas HTTP y arranque
├── tools.py          # conversión existente de definiciones de herramientas
├── upstream.py       # solicitudes HTTP a llama.cpp
├── utils.py          # JSON, SSE, identificadores y logging
└── proxy.py          # imports de compatibilidad para código anterior
tests/
├── test_config.py
├── test_import.py
└── test_proxy.py
```

## Instalación

Se requiere Python 3.11 o posterior. Para desarrollo, instala [uv](https://docs.astral.sh/uv/) y las dependencias declaradas en el grupo `dev`:

```bash
uv sync --group dev
```

La lectura TOML usa `tomllib` de la biblioteca estándar; no se agrega una dependencia de TOML.

## Ejecutar

Con los valores por defecto, el proxy escucha en `127.0.0.1:8090` y reenvía a `http://127.0.0.1:8000/v1`:

```bash
python -m codex_llamacpp_proxy
```

También se puede cambiar cada opción principal desde CLI:

```bash
python -m codex_llamacpp_proxy --host 127.0.0.1 --port 8090
python -m codex_llamacpp_proxy --port 8090
python -m codex_llamacpp_proxy --llama-base-url http://127.0.0.1:8000/v1
python -m codex_llamacpp_proxy --model modelo-local --debug
```

La ruta de entrada Responses API del cliente debe apuntar al proxy, por ejemplo `http://127.0.0.1:8090/v1`.

## Archivo TOML

Copia `config.toml.example` como `config.toml` y ajusta los valores:

```toml
[server]
host = "127.0.0.1"
port = 8090

[llama]
base_url = "http://127.0.0.1:8000/v1"
model = "modelo-local"

[proxy]
debug = false
```

Indica el archivo al arrancar:

```bash
python -m codex_llamacpp_proxy --config config.toml
```

Si no se indica `--config`, se usan los valores por defecto; no se busca ni se crea un archivo automáticamente. Un archivo indicado que no exista o contenga TOML inválido produce un error.

## Variables de entorno y precedencia

| Opción | Variable de entorno | Valor por defecto |
| --- | --- | --- |
| Host | `PROXY_HOST` | `127.0.0.1` |
| Puerto | `PROXY_PORT` | `8090` |
| URL base de llama.cpp | `LLAMA_CPP_BASE_URL` | `http://127.0.0.1:8000/v1` |
| Modelo alternativo | `LLAMA_CPP_MODEL` | vacío |
| Depuración | `PROXY_DEBUG` | `false` |

La precedencia por cada opción es **CLI > entorno > TOML > default**. Por ejemplo, la variable `LLAMA_CPP_BASE_URL` reemplaza `[llama].base_url`, y `--llama-base-url` reemplaza ambos. `PROXY_DEBUG` acepta `1`, `true`, `yes` y `on` como verdadero. El argumento `--debug` activa la depuración.

El puerto debe estar entre 1 y 65535 y la URL de llama.cpp debe ser absoluta y usar HTTP o HTTPS. Las barras finales de la URL se normalizan.

## Rutas disponibles

- `GET /health` y `GET /v1/health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`

## Tests y calidad

```bash
uv run --group dev pytest
uv run --group dev ruff check .
uv run --group dev ruff format --check .
```

## Alcance pendiente

La conversión de herramientas existente está en `tools.py`; los wrappers genéricos de herramientas Responses API permanecen allí sin cambios funcionales. No se implementa ejecución de herramientas, MCP, soporte de namespace ni búsqueda web. La conversión de mensajes Responses API está en `conversion.py` y el transporte a llama.cpp en `upstream.py`; esos son los puntos de extensión para trabajo posterior.
