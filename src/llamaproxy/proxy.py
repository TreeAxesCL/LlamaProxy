"""Backward-compatible imports; implementation lives in focused modules."""

from . import config, conversion, server, tools, upstream, utils
from .config import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_LLAMA_BASE_URL

HOST = DEFAULT_HOST
PORT = DEFAULT_PORT
LLAMA_BASE_URL = DEFAULT_LLAMA_BASE_URL
FALLBACK_MODEL = None
DEBUG = False

_MODULES = (config, conversion, server, tools, upstream, utils)


def __getattr__(name: str):
    for module in _MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
