from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .config import DEFAULT_LLAMA_BASE_URL


def llama_request(
    path: str,
    payload: dict[str, Any],
    stream: bool,
    base_url: str = DEFAULT_LLAMA_BASE_URL,
) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={
            "content-type": "application/json",
            "accept": "text/event-stream" if stream else "application/json",
        },
        method="POST",
    )
    return urlopen(req, timeout=None)


def llama_get(
    path: str, base_url: str = DEFAULT_LLAMA_BASE_URL
) -> tuple[int, bytes, str]:
    req = Request(
        base_url.rstrip("/") + path,
        headers={"accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return (
                resp.status,
                resp.read(),
                resp.headers.get("content-type", "application/json"),
            )
    except HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("content-type", "application/json")


def parse_sse_data(line: bytes) -> str | None:
    if not line.startswith(b"data:"):
        return None
    return line[5:].strip().decode("utf-8", errors="replace")
