from __future__ import annotations

import json
import logging
import traceback

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError

from .config import Config, load_config
from .conversion import (
    responses_payload_from_chat,
    responses_to_chat_request,
    responses_usage_from_chat_usage,
    stream_response_object,
)

from .upstream import llama_get, llama_request, parse_sse_data
from .utils import (
    debug,
    log,
    now_unix,
    output_id,
    read_json,
    response_id,
    send_error,
    send_json,
    sse_done,
    sse_frame,
)

from . import utils


def stream_chat_as_responses(
    handler: BaseHTTPRequestHandler, upstream: Any, model: str
) -> None:
    rid = response_id()
    oid = output_id()
    created = now_unix()
    full_text: list[str] = []

    handler.send_response(200)
    handler.send_header("content-type", "text/event-stream")
    handler.send_header("cache-control", "no-cache")
    handler.send_header("connection", "close")
    handler.close_connection = True
    handler.end_headers()

    # Helper function to write SSE frames to the client
    def write(event: str, data: Any) -> None:
        handler.wfile.write(sse_frame(event, data))
        handler.wfile.flush()

    # Create the initial response and output item structures
    response_base = {
        "id": rid,
        "object": "response",
        "created_at": created,
        "status": "in_progress",
        "model": model,
        "output": [],
    }

    # Create the initial output item structure
    output_item = {
        "id": oid,
        "type": "message",
        "status": "in_progress",
        "role": "assistant",
        "content": [],
    }

    write("response.created", {"type": "response.created", "response": response_base})

    write(
        "response.output_item.added",
        {"type": "response.output_item.added", "output_index": 0, "item": output_item},
    )

    write(
        "response.content_part.added",
        {
            "type": "response.content_part.added",
            "item_id": oid,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": "", "annotations": []},
        },
    )

    for raw in upstream:
        data_text = parse_sse_data(raw)
        if data_text is None:
            continue

        if data_text == "[DONE]":
            break

        try:
            chunk = json.loads(data_text)

        except json.JSONDecodeError:
            debug(f"bad upstream SSE data: {data_text[:200]}")
            continue

        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        piece = delta.get("content") or ""

        if not piece:
            continue

        full_text.append(piece)
        write(
            "response.output_text.delta",
            {
                "type": "response.output_text.delta",
                "item_id": oid,
                "output_index": 0,
                "content_index": 0,
                "delta": piece,
            },
        )

    # After the streaming is complete, send the final output text and mark the response as completed
    text = "".join(full_text)
    write(
        "response.output_text.done",
        {
            "type": "response.output_text.done",
            "item_id": oid,
            "output_index": 0,
            "content_index": 0,
            "text": text,
        },
    )

    # Mark the content part as completed and send the final response
    write(
        "response.content_part.done",
        {
            "type": "response.content_part.done",
            "item_id": oid,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": text, "annotations": []},
        },
    )

    # Mark the output item as completed and send the final response
    completed_item = {
        "id": oid,
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }
    write(
        "response.output_item.done",
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": completed_item,
        },
    )

    # Mark the response as completed and send the final response
    completed_response = {
        **response_base,
        "status": "completed",
        "output": [completed_item],
        "usage": responses_usage_from_chat_usage(None),
    }
    write(
        "response.completed",
        {"type": "response.completed", "response": completed_response},
    )

    handler.wfile.write(sse_done())
    handler.wfile.flush()


class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "LlamaProxy/1.0"
    config = Config()

    def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore
        debug("%s - %s" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:
        if self.path in {"/health", "/v1/health"}:
            send_json(
                self, 200, {"ok": True, "llama_base_url": self.config.llama_base_url}
            )
            return
        if self.path == "/v1/models":
            status, body, content_type = llama_get(
                "/models", self.config.llama_base_url
            )
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        send_error(self, 404, f"unknown endpoint: {self.path}")

    def do_POST(self) -> None:
        try:
            if self.path == "/v1/chat/completions":
                payload = read_json(self)
                stream = bool(payload.get("stream"))

                upstream = llama_request(
                    "/chat/completions", payload, stream, self.config.llama_base_url
                )

                if stream:
                    self.send_response(upstream.status)
                    self.send_header(
                        "content-type",
                        upstream.headers.get("content-type", "text/event-stream"),
                    )

                    self.end_headers()
                    for chunk in upstream:
                        self.wfile.write(chunk)
                    self.wfile.flush()

                else:
                    body = upstream.read()
                    self.send_response(upstream.status)
                    self.send_header(
                        "content-type",
                        upstream.headers.get("content-type", "application/json"),
                    )

                    self.send_header("content-length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                return

            if self.path != "/v1/responses":
                send_error(self, 404, f"unknown endpoint: {self.path}")
                return

            payload = read_json(self)

            # Debug logging of the request payload, including previous_response_id, input types, and function call outputs.
            debug(
                json.dumps(
                    {
                        "responses_request": {
                            "previous_response_id": payload.get("previous_response_id"),
                            "input_types": [
                                item.get("type")
                                for item in payload.get("input", [])
                                if isinstance(item, dict)
                            ],
                            "function_call_outputs": [
                                {
                                    "call_id": item.get("call_id"),
                                    "type": item.get("type"),
                                }
                                for item in payload.get("input", [])
                                if isinstance(item, dict)
                                and item.get("type") == "function_call_output"
                            ],
                        }
                    },
                    ensure_ascii=False,
                )
            )

            # Convert the Responses request payload to a Chat Completions request payload
            chat_payload = responses_to_chat_request(payload, self.config.model)
            debug(json.dumps({"chat_payload": chat_payload}, ensure_ascii=False)[:4000])

            client_wants_stream = bool(chat_payload.get("stream"))
            # Use a non-streaming upstream call for Responses requests so tool_calls
            # can be converted into complete Responses function_call items.
            chat_payload["stream"] = False
            upstream = llama_request(
                "/chat/completions", chat_payload, False, self.config.llama_base_url
            )

            # Read the upstream response body and convert it to a Responses response payload
            chat_body = upstream.read()
            chat_json = json.loads(chat_body.decode("utf-8"))
            responses_json = responses_payload_from_chat(
                chat_json, chat_payload["model"]
            )

            # If the client requested streaming, stream the Responses response payload as SSE events.
            if client_wants_stream:
                stream_response_object(self, responses_json)
                return

            send_json(self, 200, responses_json)

        except HTTPError as exc:
            body = exc.read()
            self.send_response(exc.code)
            self.send_header(
                "content-type", exc.headers.get("content-type", "application/json")
            )
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        except (URLError, ConnectionError) as exc:
            send_error(
                self,
                502,
                f"Failed to reach llama.cpp at {self.config.llama_base_url}: {exc}",
            )

        except Exception as exc:
            if self.config.debug:
                traceback.print_exc()
            send_error(self, 500, str(exc))


def main() -> int:
    config = load_config()

    utils.DEBUG = config.debug
    logging.basicConfig(level=logging.DEBUG if config.debug else logging.INFO)

    utils.logger.setLevel("DEBUG" if config.debug else "INFO")
    handler = type("ConfiguredProxyHandler", (ProxyHandler,), {"config": config})

    server = ThreadingHTTPServer((config.host, config.port), handler)

    log(f" Proxy listening on http://{config.host}:{config.port}/v1")
    log(f" Forwarding to {config.llama_base_url}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log(" Stopping the Proxy...")
        return 0
    return 0
