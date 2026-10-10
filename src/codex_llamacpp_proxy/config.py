"""Load proxy settings from TOML, environment, and command-line arguments."""

from __future__ import annotations

import argparse
import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8090
DEFAULT_LLAMA_BASE_URL = "http://127.0.0.1:8000/v1"


@dataclass(frozen=True)
class Config:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    llama_base_url: str = DEFAULT_LLAMA_BASE_URL
    model: str | None = None
    debug: bool = False


class ConfigError(ValueError):
    """Invalid proxy configuration."""


def _validate(config: Config) -> Config:
    if isinstance(config.port, bool) or not isinstance(config.port, int):
        raise ConfigError("port must be an integer")

    if not 1 <= config.port <= 65535:
        raise ConfigError("port must be between 1 and 65535")

    if not isinstance(config.host, str) or not config.host.strip():
        raise ConfigError("host must not be empty")

    if not isinstance(config.llama_base_url, str):
        raise ConfigError("llama base URL must be a string")

    url = config.llama_base_url.rstrip("/")
    parsed = urlsplit(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError("llama base URL must be an absolute HTTP or HTTPS URL")

    if not isinstance(config.debug, bool):
        raise ConfigError("proxy.debug must be a boolean")

    if config.model is not None and not isinstance(config.model, str):
        raise ConfigError("llama.model must be a string")

    return replace(config, llama_base_url=url)


def _read_toml(path: Path) -> Config:
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)

    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc

    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc

    try:
        server = data.get("server", {})
        llama = data.get("llama", {})
        proxy = data.get("proxy", {})

        return Config(
            host=server.get("host", DEFAULT_HOST),
            port=server.get("port", DEFAULT_PORT),
            llama_base_url=llama.get("base_url", DEFAULT_LLAMA_BASE_URL),
            model=llama.get("model") or None,
            debug=proxy.get("debug", False),
        )

    except AttributeError as exc:
        raise ConfigError("config sections must be TOML tables") from exc


def load_config(
    argv: list[str] | None = None, environ: Mapping[str, str] | None = None
) -> Config:
    """Resolve settings in CLI > environment > TOML > defaults order."""
    env = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(description="Responses API to llama.cpp proxy")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--llama-base-url")
    parser.add_argument("--model")
    parser.add_argument("--debug", action="store_true", default=None)
    args = parser.parse_args(argv)

    base = _read_toml(args.config) if args.config else Config()
    try:
        configured = replace(
            base,
            host=env.get("PROXY_HOST", base.host),
            port=int(env.get("PROXY_PORT", base.port)),
            llama_base_url=env.get("LLAMA_CPP_BASE_URL", base.llama_base_url),
            model=env.get("LLAMA_CPP_MODEL", base.model) or None,
            debug=env.get("PROXY_DEBUG", str(base.debug)).lower()
            in {"1", "true", "yes", "on"},
        )

    except ValueError as exc:
        raise ConfigError(f"invalid environment configuration: {exc}") from exc

    return _validate(
        replace(
            configured,
            host=args.host if args.host is not None else configured.host,
            port=args.port if args.port is not None else configured.port,
            llama_base_url=args.llama_base_url
            if args.llama_base_url is not None
            else configured.llama_base_url,
            model=args.model if args.model is not None else configured.model,
            debug=args.debug if args.debug is not None else configured.debug,
        )
    )
