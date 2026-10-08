from __future__ import annotations

import json
import logging
import time
import uuid
from http.server import BaseHTTPRequestHandler
from typing import Any

logger = logging.getLogger("codex_llamacpp_proxy")
DEBUG = False


def log(message: str) -> None:
    logger.info(message)


def debug(message: str) -> None:
    if DEBUG:
        logger.debug(message)


def now_unix() -> int:
    return int(time.time())


def response_id() -> str:
    return "resp_" + uuid.uuid4().hex


def output_id() -> str:
    return "msg_" + uuid.uuid4().hex


def call_id() -> str:
    return "call_" + uuid.uuid4().hex


def error_payload(message: str, status: int = 400, code: str = "proxy_error") -> bytes:
    return json.dumps(
        {
            "error": {
                "message": message,
                "type": "invalid_request_error" if status < 500 else "server_error",
                "code": code,
            }
        },
        ensure_ascii=False,
    ).encode("utf-8")


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("content-length") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def send_json(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json")
    handler.send_header("content-length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_error(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    body = error_payload(message, status)
    handler.send_response(status)
    handler.send_header("content-type", "application/json")
    handler.send_header("content-length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def sse_frame(event: str, data: Any) -> bytes:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {text}\n\n".encode("utf-8")


def sse_done() -> bytes:
    return b"data: [DONE]\n\n"
