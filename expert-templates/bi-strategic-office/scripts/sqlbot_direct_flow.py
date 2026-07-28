#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import re
import sys
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client


DEFAULT_URL = "http://192.168.102.247:18001/mcp"
DEFAULT_QUESTION = "查询应收交易编号 101IN26070199 的交易明细"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SQLBot MCP 完整直连测试"
    )

    parser.add_argument(
        "--url",
        default=os.getenv("SQLBOT_MCP_URL", DEFAULT_URL),
    )
    parser.add_argument(
        "--username",
        default=os.getenv("SQLBOT_USERNAME", ""),
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SQLBOT_PASSWORD", ""),
    )
    parser.add_argument(
        "--oid",
        default=os.getenv("SQLBOT_WORKSPACE_ID", ""),
    )
    parser.add_argument(
        "--datasource-id",
        default=os.getenv(
            "SQLBOT_DEFAULT_DATASOURCE_ID",
            "",
        ),
    )
    parser.add_argument(
        "--question",
        default=os.getenv(
            "SQLBOT_TEST_QUESTION",
            DEFAULT_QUESTION,
        ),
    )
    parser.add_argument(
        "--followup",
        default=os.getenv(
            "SQLBOT_TEST_FOLLOWUP",
            "",
        ),
    )

    return parser.parse_args()


def strip_json_fence(text: str) -> str:
    value = text.strip()

    match = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        value,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return value


def parse_json_text(text: str) -> Any:
    value = strip_json_fence(text)

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    start = value.find("{")
    end = value.rfind("}")

    if start >= 0 and end > start:
        try:
            return json.loads(value[start : end + 1])
        except json.JSONDecodeError:
            pass

    start = value.find("[")
    end = value.rfind("]")

    if start >= 0 and end > start:
        try:
            return json.loads(value[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}

        for key, item in value.items():
            lowered = key.lower()

            if any(
                marker in lowered
                for marker in (
                    "password",
                    "access_token",
                    "sqlbot_token",
                    "secret",
                    "authorization",
                )
            ):
                result[key] = "***REDACTED***"
            else:
                result[key] = redact(item)

        return result

    if isinstance(value, list):
        return [redact(item) for item in value]

    return value


def result_texts(result: Any) -> list[str]:
    texts: list[str] = []

    for content in result.content or []:
        text = getattr(content, "text", None)

        if text is not None:
            texts.append(text)
        else:
            texts.append(str(content))

    return texts


def parse_result(result: Any) -> Any:
    texts = result_texts(result)

    for text in texts:
        parsed = parse_json_text(text)

        if parsed is not None:
            return parsed

    structured = getattr(
        result,
        "structuredContent",
        None,
    )

    if structured is not None:
        return structured

    return {
        "texts": texts,
    }


def print_result(
    tool_name: str,
    result: Any,
) -> Any:
    payload = parse_result(result)

    print(f"\n===== {tool_name} =====")
    print(
        json.dumps(
            redact(payload),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    if getattr(result, "isError", False):
        raise RuntimeError(
            f"{tool_name} 返回 MCP Tool Error"
        )

    if isinstance(payload, dict):
        code = payload.get("code")

        if code not in (None, 0, "0"):
            raise RuntimeError(
                f"{tool_name} 返回业务错误："
                f"{payload.get('msg') or payload}"
            )

    return payload


async def call_tool(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    print(f"\n>>> 调用 {name}")

    safe_args = redact(arguments)

    print(
        json.dumps(
            safe_args,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    result = await session.call_tool(
        name,
        arguments=arguments,
    )

    return print_result(name, result)


def business_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]

    return payload


def extract_start(payload: Any) -> tuple[str, int]:
    data = business_data(payload)

    if not isinstance(data, dict):
        raise RuntimeError(
            "mcp_start 返回 data 不是对象"
        )

    token = (
        data.get("access_token")
        or data.get("sqlbot_token")
        or data.get("token")
    )

    chat_id = (
        data.get("chat_id")
        or data.get("sqlbot_chat_id")
    )

    if not token:
        raise RuntimeError(
            "mcp_start 未返回 access_token"
        )

    if chat_id is None:
        raise RuntimeError(
            "mcp_start 未返回 chat_id"
        )

    return str(token), int(chat_id)


def first_record(payload: Any) -> dict[str, Any] | None:
    data = business_data(payload)

    if not isinstance(data, list):
        return None

    if not data:
        return None

    first = data[0]

    if not isinstance(first, dict):
        return None

    return first


def extract_workspace_id(payload: Any) -> str | None:
    row = first_record(payload)

    if row is None:
        return None

    value = row.get("id") or row.get("oid")

    if value is None:
        return None

    return str(value)


def extract_datasource_id(payload: Any) -> str | None:
    row = first_record(payload)

    if row is None:
        return None

    value = (
        row.get("id")
        or row.get("datasource_id")
    )

    if value is None:
        return None

    return str(value)


async def run(args: argparse.Namespace) -> None:
    username = args.username.strip()
    password = args.password

    if not username:
        username = input("SQLBot username: ").strip()

    if not password:
        password = getpass.getpass(
            "SQLBot password: "
        )

    if not username or not password:
        raise RuntimeError(
            "用户名和密码不能为空"
        )

    print("===== SQLBOT MCP DIRECT FLOW =====")
    print(f"MCP URL: {args.url}")

    async with sse_client(
        args.url
    ) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:
            initialized = await session.initialize()

            print(
                "MCP Server:",
                getattr(
                    initialized,
                    "serverInfo",
                    None,
                ),
            )

            await session.send_ping()
            print("MCP Ping: OK")

            # 1. 登录并创建问数会话
            start_payload = await call_tool(
                session,
                "mcp_start",
                {
                    "username": username,
                    "password": password,
                },
            )

            token, chat_id = extract_start(
                start_payload
            )

            print("\n登录成功")
            print(f"chat_id: {chat_id}")
            print("access_token: ***REDACTED***")

            # 2. 工作空间
            workspace_payload = await call_tool(
                session,
                "mcp_ws_list",
                {
                    "token": token,
                },
            )

            oid = (
                args.oid.strip()
                or extract_workspace_id(
                    workspace_payload
                )
            )

            if oid:
                print(f"\n选定 workspace oid: {oid}")
            else:
                print(
                    "\n没有自动取得 workspace，"
                    "将使用 SQLBot 最后登录工作空间"
                )

            # 3. 数据源
            datasource_args: dict[str, Any] = {
                "token": token,
            }

            if oid:
                datasource_args["oid"] = oid

            datasource_payload = await call_tool(
                session,
                "mcp_datasource_list",
                datasource_args,
            )

            datasource_id = (
                args.datasource_id.strip()
                or extract_datasource_id(
                    datasource_payload
                )
            )

            if datasource_id:
                print(
                    "\n选定 datasource_id: "
                    f"{datasource_id}"
                )
            else:
                print(
                    "\n没有自动取得数据源，"
                    "mcp_question 将使用默认数据源"
                )

            # 4. 首轮问数
            question_args: dict[str, Any] = {
                "token": token,
                "chat_id": chat_id,
                "question": args.question,
                "stream": False,
                "lang": "zh-CN",
                "return_img": False,
            }

            if datasource_id:
                question_args[
                    "datasource_id"
                ] = datasource_id
            elif oid:
                question_args["oid"] = oid

            await call_tool(
                session,
                "mcp_question",
                question_args,
            )

            # 5. 连续追问
            if args.followup.strip():
                await call_tool(
                    session,
                    "mcp_question",
                    {
                        "token": token,
                        "chat_id": chat_id,
                        "question": (
                            args.followup.strip()
                        ),
                        "stream": False,
                        "lang": "zh-CN",
                        "return_img": False,
                    },
                )

            print(
                "\n===== SQLBOT DIRECT FLOW PASSED ====="
            )


def main() -> int:
    args = parse_args()

    try:
        asyncio.run(run(args))
        return 0

    except KeyboardInterrupt:
        print(
            "\n测试已取消",
            file=sys.stderr,
        )
        return 130

    except Exception as exc:
        print(
            f"\n测试失败："
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())