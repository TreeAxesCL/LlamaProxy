from __future__ import annotations

import re
from typing import Any

from .utils import debug


def convert_tool(tool: Any) -> dict[str, Any] | None:
    if not isinstance(tool, dict):
        return None
    if tool.get("type") != "function":
        return wrap_responses_tool_as_function(tool)

    if isinstance(tool.get("function"), dict):
        function = dict(tool["function"])
    else:
        function = {
            "name": tool.get("name"),
            "description": tool.get("description", ""),
            "parameters": tool.get("parameters") or {},
        }

    if not function.get("name"):
        return None

    if not isinstance(function.get("parameters"), dict):
        function["parameters"] = {}

    return {"type": "function", "function": function}


def sanitize_function_name(value: Any) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "tool")).strip("_")
    if not name:
        name = "tool"

    if len(name) > 64:
        name = name[:64].rstrip("_-") or "tool"

    return name


def default_parameters_for_responses_tool(tool_type: str) -> dict[str, Any]:
    if "web_search" in tool_type or tool_type in {"search", "browser_search"}:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                }
            },
            "required": ["query"],
            "additionalProperties": True,
        }

    if "image_generation" in tool_type or "image" in tool_type:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Image generation prompt.",
                }
            },
            "required": ["prompt"],
            "additionalProperties": True,
        }

    if "computer" in tool_type:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Computer action to perform.",
                }
            },
            "required": ["action"],
            "additionalProperties": True,
        }

    return {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }


def wrap_responses_tool_as_function(tool: dict[str, Any]) -> dict[str, Any] | None:
    tool_type = str(tool.get("type") or "tool")
    name = sanitize_function_name(tool.get("name") or tool_type)

    parameters = (
        tool.get("parameters") or tool.get("input_schema") or tool.get("schema")
    )

    if not isinstance(parameters, dict):
        parameters = default_parameters_for_responses_tool(tool_type)

    description = tool.get("description")
    if not isinstance(description, str) or not description.strip():
        description = (
            f"Proxy wrapper for the Responses API tool '{tool_type}'. "
            "Call this function when that tool is needed."
        )

    debug(f"rewriting Responses tool {tool_type!r} as function {name!r}")
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def convert_tools(tools: Any) -> list[dict[str, Any]]:
    if not isinstance(tools, list):
        return []

    converted = [
        converted for tool in tools if (converted := convert_tool(tool)) is not None
    ]

    debug(f"tools: received={len(tools)} forwarded={len(converted)}")
    return converted


def convert_tool_choice(choice: Any, tools: list[dict[str, Any]]) -> Any:
    if not tools:
        return None

    if choice in (None, "auto", "none", "required"):
        return choice

    if isinstance(choice, dict):
        if choice.get("type") == "function":
            if isinstance(choice.get("function"), dict):
                return choice

            if choice.get("name"):
                return {"type": "function", "function": {"name": choice["name"]}}

        if choice.get("type") in {"auto", "none", "required"}:
            return choice["type"]
    return "auto"
