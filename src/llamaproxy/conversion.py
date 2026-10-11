from __future__ import annotations

import json
import uuid
from http.server import BaseHTTPRequestHandler
from typing import Any

from .tools import convert_tool_choice, convert_tools
from .utils import call_id, debug, now_unix, output_id, response_id, sse_done, sse_frame


def text_from_content_part(part: Any) -> str:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ""

    part_type = part.get("type")
    if part_type in {"input_text", "output_text", "text"}:
        return str(part.get("text") or "")

    if part_type in {"input_image", "image_url"}:
        return "[image omitted by local proxy]"

    if part_type in {"file", "input_file"}:
        name = part.get("filename") or part.get("file_id") or "file"
        return f"[file omitted by local proxy: {name}]"

    if part_type in {"function_call_output", "tool_result"}:
        return str(part.get("output") or part.get("content") or "")

    return str(part.get("text") or part.get("content") or "")


def normalize_role(role: str | None) -> str:
    if role in {"system", "user", "assistant", "tool"}:
        return role

    if role == "developer":
        return "system"

    return "user"


def input_item_to_message(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        return {"role": "user", "content": item}

    if not isinstance(item, dict):
        return None

    item_type = item.get("type")
    if item_type == "message" or "role" in item:
        role = normalize_role(item.get("role"))
        content = item.get("content", "")

        if isinstance(content, list):
            content = "\n".join(
                filter(None, (text_from_content_part(part) for part in content))
            )

        elif not isinstance(content, str):
            content = text_from_content_part(content)
        message: dict[str, Any] = {"role": role, "content": content}

        if role == "tool" and item.get("call_id"):
            message["tool_call_id"] = item["call_id"]
        return message

    if item_type == "function_call":
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": item.get("call_id", ""),
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": item.get("arguments", "{}"),
                    },
                }
            ],
        }

    if item_type in {"function_call_output", "tool_result"}:
        content = str(item.get("output") or item.get("content") or "")
        message = {"role": "tool", "content": content}

        if item.get("call_id"):
            message["tool_call_id"] = item["call_id"]
        return message

    if item_type in {"input_text", "text"}:
        return {"role": "user", "content": str(item.get("text") or "")}

    return {"role": "user", "content": text_from_content_part(item)}


def responses_input_to_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    instructions = payload.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions})

    input_value = payload.get("input", "")
    if isinstance(input_value, str):
        messages.append({"role": "user", "content": input_value})

    elif isinstance(input_value, list):
        for item in input_value:
            message = input_item_to_message(item)
            if message is not None:
                messages.append(message)

    elif isinstance(input_value, dict):
        message = input_item_to_message(input_value)
        if message is not None:
            messages.append(message)

    if not messages:
        messages.append({"role": "user", "content": ""})
    messages = strip_assistant_prefill(messages)

    return messages


def strip_assistant_prefill(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Avoid llama.cpp/Qwen treating a trailing assistant message as prefill.

    Codex Responses requests may include prior assistant output items in the
    input list. Qwen chat templates with enable_thinking reject assistant
    prefill, so never forward a Chat Completions request ending in assistant.
    """
    if not messages:
        return messages

    stripped = list(messages)
    while len(stripped) > 1 and stripped[-1].get("role") == "assistant":
        removed = stripped.pop()
        debug(
            f"dropping trailing assistant prefill: {str(removed.get('content') or '')[:120]!r}"
        )

    if stripped and stripped[-1].get("role") == "assistant":
        content = str(stripped[-1].get("content") or "")
        stripped[-1] = {
            "role": "user",
            "content": (
                "Previous assistant response, preserved as context rather than "
                f"assistant prefill:\n{content}"
            ),
        }

    return stripped


def responses_to_chat_request(
    payload: dict[str, Any], fallback_model: str | None = None
) -> dict[str, Any]:
    model = payload.get("model") or fallback_model
    if not model:
        raise ValueError("missing model; set model in the request or LLAMA_CPP_MODEL")

    chat: dict[str, Any] = {
        "model": model,
        "messages": responses_input_to_messages(payload),
        "stream": bool(payload.get("stream")),
    }

    passthrough = [
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "stop",
    ]
    for key in passthrough:
        if key in payload and payload[key] is not None:
            chat[key] = payload[key]

    if "max_output_tokens" in payload and payload["max_output_tokens"] is not None:
        chat["max_tokens"] = payload["max_output_tokens"]

    tools = convert_tools(payload.get("tools"))
    if tools:
        chat["tools"] = tools
        tool_choice = convert_tool_choice(payload.get("tool_choice"), tools)
        if tool_choice is not None:
            chat["tool_choice"] = tool_choice

    return chat


def chat_message_to_output_text(message: dict[str, Any]) -> str:
    content = message.get("content")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "\n".join(
            filter(None, (text_from_content_part(part) for part in content))
        )

    return "" if content is None else str(content)


def normalize_tool_arguments(arguments: Any) -> str:
    if isinstance(arguments, str):
        return arguments

    if arguments is None:
        return "{}"

    return json.dumps(arguments, ensure_ascii=False)


def chat_tool_calls_to_response_items(message: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    tool_calls = message.get("tool_calls")

    if not isinstance(tool_calls, list):
        return items

    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue

        function_value = tool_call.get("function")
        function = function_value if isinstance(function_value, dict) else {}

        name = function.get("name") or tool_call.get("name")
        if not name:
            continue
        items.append(
            {
                "id": "fc_" + uuid.uuid4().hex,
                "type": "function_call",
                "call_id": str(tool_call.get("id") or call_id()),
                "name": str(name),
                "arguments": normalize_tool_arguments(
                    function.get("arguments") or tool_call.get("arguments")
                ),
            }
        )

    return items


def responses_usage_from_chat_usage(usage: Any) -> dict[str, Any]:
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(
        usage.get("output_tokens") or usage.get("completion_tokens") or 0
    )

    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

    input_details = usage.get("input_tokens_details")
    if not isinstance(input_details, dict):
        input_details = {}

    output_details = usage.get("output_tokens_details")
    if not isinstance(output_details, dict):
        output_details = {}

    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {
            "cached_tokens": int(
                input_details.get("cached_tokens")
                or usage.get("prompt_tokens_cached")
                or 0
            ),
        },
        "output_tokens": output_tokens,
        "output_tokens_details": {
            "reasoning_tokens": int(output_details.get("reasoning_tokens") or 0),
        },
        "total_tokens": total_tokens,
    }


def responses_payload_from_chat(
    chat_payload: dict[str, Any], model: str, rid: str | None = None
) -> dict[str, Any]:
    rid = rid or response_id()
    choice = (chat_payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = chat_message_to_output_text(message)

    output_items = chat_tool_calls_to_response_items(message)
    if text or not output_items:
        oid = output_id()
        output_items.insert(
            0,
            {
                "id": oid,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            },
        )

    created = chat_payload.get("created") or now_unix()
    usage = responses_usage_from_chat_usage(chat_payload.get("usage"))

    return {
        "id": rid,
        "object": "response",
        "created_at": created,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "max_output_tokens": None,
        "model": model,
        "output": output_items,
        "parallel_tool_calls": True,
        "temperature": None,
        "tool_choice": "auto",
        "tools": [],
        "top_p": None,
        "usage": usage,
    }


def stream_response_object(
    handler: BaseHTTPRequestHandler, response: dict[str, Any]
) -> None:
    handler.send_response(200)
    handler.send_header("content-type", "text/event-stream")
    handler.send_header("cache-control", "no-cache")
    handler.send_header("connection", "close")
    handler.close_connection = True
    handler.end_headers()

    started = dict(response)
    started["status"] = "in_progress"
    started["output"] = []
    handler.wfile.write(
        sse_frame("response.created", {"type": "response.created", "response": started})
    )

    for index, item in enumerate(response.get("output") or []):
        added = dict(item)
        if added.get("type") == "message":
            added["status"] = "in_progress"
            added["content"] = []
        handler.wfile.write(
            sse_frame(
                "response.output_item.added",
                {
                    "type": "response.output_item.added",
                    "output_index": index,
                    "item": added,
                },
            )
        )

        if item.get("type") == "message":
            content = item.get("content") or []
            part = (
                content[0]
                if content
                else {"type": "output_text", "text": "", "annotations": []}
            )

            text = str(part.get("text") or "")
            handler.wfile.write(
                sse_frame(
                    "response.content_part.added",
                    {
                        "type": "response.content_part.added",
                        "item_id": item.get("id"),
                        "output_index": index,
                        "content_index": 0,
                        "part": {"type": "output_text", "text": "", "annotations": []},
                    },
                )
            )

            if text:
                handler.wfile.write(
                    sse_frame(
                        "response.output_text.delta",
                        {
                            "type": "response.output_text.delta",
                            "item_id": item.get("id"),
                            "output_index": index,
                            "content_index": 0,
                            "delta": text,
                        },
                    )
                )

            handler.wfile.write(
                sse_frame(
                    "response.output_text.done",
                    {
                        "type": "response.output_text.done",
                        "item_id": item.get("id"),
                        "output_index": index,
                        "content_index": 0,
                        "text": text,
                    },
                )
            )

            handler.wfile.write(
                sse_frame(
                    "response.content_part.done",
                    {
                        "type": "response.content_part.done",
                        "item_id": item.get("id"),
                        "output_index": index,
                        "content_index": 0,
                        "part": part,
                    },
                )
            )

        handler.wfile.write(
            sse_frame(
                "response.output_item.done",
                {
                    "type": "response.output_item.done",
                    "output_index": index,
                    "item": item,
                },
            )
        )

    handler.wfile.write(
        sse_frame(
            "response.completed", {"type": "response.completed", "response": response}
        )
    )

    handler.wfile.write(sse_done())
    handler.wfile.flush()
