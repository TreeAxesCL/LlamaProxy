from __future__ import annotations

import pytest

from codex_llamacpp_proxy.config import (
    Config,
    ConfigError,
    DEFAULT_LLAMA_BASE_URL,
    load_config,
)


def test_defaults() -> None:
    assert load_config([], {}).llama_base_url == DEFAULT_LLAMA_BASE_URL
    assert load_config([], {}) == Config()


def test_toml_config(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[server]\nhost="0.0.0.0"\nport=9000\n'
        '[llama]\nbase_url="http://localhost:8000/v1/"\nmodel="local"\n'
        "[proxy]\ndebug=true\n",
        encoding="utf-8",
    )
    assert load_config(["--config", str(path)], {}) == Config(
        "0.0.0.0", 9000, "http://localhost:8000/v1", "local", True
    )


def test_environment_overrides_toml(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[server]\nport=9000\n", encoding="utf-8")
    config = load_config(["--config", str(path)], {"PROXY_PORT": "9001"})
    assert config.port == 9001


def test_cli_overrides_environment_and_toml(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[server]\nport=9000\n", encoding="utf-8")
    config = load_config(
        ["--config", str(path), "--port", "9002"], {"PROXY_PORT": "9001"}
    )
    assert config.port == 9002


def test_cli_and_environment_values() -> None:
    config = load_config(
        ["--host", "cli", "--llama-base-url", "http://cli/v1", "--debug"],
        {"PROXY_HOST": "env", "LLAMA_CPP_BASE_URL": "http://env/v1"},
    )
    assert (config.host, config.llama_base_url, config.debug) == (
        "cli",
        "http://cli/v1",
        True,
    )


@pytest.mark.parametrize("port", ["0", "65536", "-1", "nope"])
def test_invalid_environment_port(port: str) -> None:
    with pytest.raises(ConfigError):
        load_config([], {"PROXY_PORT": port})


def test_invalid_cli_port() -> None:
    with pytest.raises(ConfigError):
        load_config(["--port", "70000"], {})


def test_invalid_toml_and_missing_file(tmp_path) -> None:
    invalid = tmp_path / "invalid.toml"
    invalid.write_text("[server\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(["--config", str(invalid)], {})
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(["--config", str(tmp_path / "missing.toml")], {})


def test_invalid_url() -> None:
    with pytest.raises(ConfigError, match="absolute HTTP"):
        load_config(["--llama-base-url", "localhost:8000/v1"], {})


def test_config_option_is_optional() -> None:
    assert load_config([], {}) == Config()
