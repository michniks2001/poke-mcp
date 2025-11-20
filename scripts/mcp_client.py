"""Utility script to exercise the poke-mcp FastMCP server via HTTP.

Usage:
    python scripts/mcp_client.py --url http://localhost:3333/mcp --tool parse_smogon_team --param team_text@team1.txt

Parameters can be provided inline (key=value) or by referencing files via the
`key@path/to/file` syntax to avoid shell quoting issues.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastmcp import Client


def _parse_param(arg: str) -> tuple[str, Any]:
    if "=" in arg:
        key, value = arg.split("=", 1)
        return key, value
    if "@" in arg:
        key, filepath = arg.split("@", 1)
        text = Path(filepath).read_text(encoding="utf-8")
        return key, text
    raise argparse.ArgumentTypeError(
        "Parameters must be in key=value or key@/path/to/file format"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://localhost:3333/mcp",
        help="Base MCP endpoint exposed by the FastMCP server",
    )
    parser.add_argument(
        "--tool",
        default="parse_smogon_team",
        help="Tool name to invoke (use list-tools to inspect options)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available tools/resources/prompts instead of calling a tool",
    )
    parser.add_argument(
        "params",
        nargs="*",
        type=_parse_param,
        help="Tool parameters as key=value or key@file",
    )
    return parser


def _params_to_dict(pairs: list[tuple[str, Any]] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if not pairs:
        return payload
    for key, value in pairs:
        payload[key] = value
    return payload


async def _list_capabilities(client: Client) -> None:
    def _field(item: Any, key: str, default: str = "") -> str:
        if isinstance(item, dict):
            return str(item.get(key, default))
        return str(getattr(item, key, default))

    tools = await client.list_tools()
    resources = await client.list_resources()
    prompts = await client.list_prompts()

    print("\n== Tools ==")
    for tool in tools:
        print(f"- {_field(tool, 'name')}: {_field(tool, 'description')}")

    print("\n== Resources ==")
    for resource in resources:
        uri = _field(resource, 'uri', _field(resource, 'uri_template'))
        print(f"- {_field(resource, 'name') or uri} ({uri})")

    print("\n== Prompts ==")
    for prompt in prompts:
        print(f"- {_field(prompt, 'name')}")


def _coerce(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {k: _coerce(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_coerce(item) for item in value]
    if is_dataclass(value):
        return _coerce(asdict(value))
    for attr in ("model_dump", "dict", "to_dict"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return _coerce(method())
            except TypeError:
                continue
    return str(value)


async def _call_tool(client: Client, tool: str, params: dict[str, Any]) -> None:
    result = await client.call_tool(tool, params)
    print(json.dumps(_coerce(result), indent=2))


async def _main_async() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    async with Client(args.url) as client:
        await client.ping()
        if args.list:
            await _list_capabilities(client)
            return

        params = _params_to_dict(args.params)
        await _call_tool(client, args.tool, params)


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
