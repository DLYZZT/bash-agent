from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.status import Status

from .config import Config
from .security import (
    BashResult,
    is_obviously_dangerous,
    is_outside_workdir,
    run_bash,
)
from .logger import get_logger

logger = get_logger(__name__)


class ToolHandler:

    def __init__(
        self,
        config: Config,
        console: Console,
        confirm: Callable[[str], bool],
        mcp_manager: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.console = console
        self.confirm = confirm
        self.mcp_manager = mcp_manager

    def get_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "bash_exec",
                    "description": (
                        "Execute a shell command inside the isolated working directory: "
                        f"{self.config.work_dir}. Current OS: {self.config.os_name}, "
                        f"Shell: {self.config.shell_type}."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": f"The shell command string to execute (using {self.config.shell_type})",
                            },
                            "timeout_s": {
                                "type": "integer",
                                "description": "Timeout seconds (default 30)",
                                "minimum": 1,
                            },
                        },
                        "required": ["command"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

        if self.mcp_manager and self.mcp_manager.is_connected():
            tools.extend(self.mcp_manager.get_tools_for_openai())

        return tools

    def handle_tool_calls(self, messages: List[Dict[str, Any]], tool_calls) -> None:
        logger.info(f"开始处理 {len(tool_calls)} 个工具调用")
        for tool_call in tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")
            logger.debug(f"工具调用: {name}, 参数: {str(args)[:100]}")

            if name == "bash_exec":
                payload = self._handle_bash_exec(args)
            elif name.startswith("mcp_"):
                payload = self._handle_mcp_tool(name, args)
            else:
                logger.warning(f"未知工具: {name}")
                payload = {"ok": False, "error": "unknown tool"}

            logger.debug(f"工具 {name} 执行结果: ok={payload.get('ok', False)}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            )

    def _handle_bash_exec(self, args: Dict[str, Any]) -> Dict[str, Any]:
        command = args.get("command", "")
        timeout_s = int(args.get("timeout_s", 30))
        logger.info(f"bash_exec 工具被调用: {command[:100]}{'...' if len(command) > 100 else ''}")

        if is_obviously_dangerous(command):
            logger.warning(f"bash_exec: 危险命令被拦截 - {command[:50]}")
            return {
                "ok": False,
                "ran": False,
                "reason": "dangerous_command_blocked",
                "stdout": "",
                "stderr": "blocked by guard",
                "exit_code": 1,
            }

        if is_outside_workdir(command, self.config.work_dir):
            logger.warning(f"bash_exec: 路径越界被拦截 - {command[:50]}")
            return {
                "ok": False,
                "ran": False,
                "reason": "outside_workdir_blocked",
                "stdout": "",
                "stderr": f"must stay inside {self.config.work_dir}",
                "exit_code": 1,
            }

        if not self.confirm(command):
            logger.info("bash_exec: 用户取消了命令执行")
            self.console.print("[bold yellow]⏸️  用户取消了命令执行[/bold yellow]")
            declined = BashResult("", "user declined", 1, ran=False, reason="declined")
            return {
                "ok": False,
                "ran": declined.ran,
                "reason": declined.reason,
                "stdout": declined.stdout,
                "stderr": declined.stderr,
                "exit_code": declined.exit_code,
            }

        with Status("[bold blue]执行命令中...", spinner="dots"):
            result = run_bash(command, self.config, timeout_s=timeout_s)

        if result.exit_code == 0 and result.ran:
            self.console.print("[bold green]✅ 命令执行成功[/bold green]")
        else:
            self.console.print("[bold red]❌ 命令执行失败[/bold red]")

        if result.stdout:
            self.console.print(f"[cyan]输出:[/cyan] {result.stdout}")
        if result.stderr:
            self.console.print(f"[red]错误:[/red] {result.stderr}")
        if result.reason:
            self.console.print(f"[yellow]原因:[/yellow] {result.reason}")

        return {
            "ok": result.exit_code == 0 and result.ran,
            "ran": result.ran,
            "reason": result.reason,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
        }

    def _handle_mcp_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"MCP 工具被调用: {name}")
        if not self.mcp_manager or not self.mcp_manager.is_connected():
            logger.error("MCP 工具调用失败: 客户端未连接")
            return {"ok": False, "error": "MCP 客户端未连接"}

        parts = name[4:].split("_", 1)
        if len(parts) == 2:
            server_name, tool_name = parts
            logger.debug(f"MCP 工具详情: 服务器={server_name}, 工具={tool_name}")
            self.console.print(f"[bold blue]🔧 调用 MCP 工具: [{server_name}] {tool_name}[/bold blue]")
        else:
            self.console.print(f"[bold blue]🔧 调用 MCP 工具: {name}[/bold blue]")

        with Status("[bold blue]执行 MCP 工具...", spinner="dots"):
            result = self.mcp_manager.call_tool(name, args)

        if result.get("success"):
            logger.info(f"MCP 工具执行成功: {name}")
            self.console.print("[bold green]✅ MCP 工具执行成功[/bold green]")
            return {
                "ok": True,
                "content": result.get("content", []),
                "is_error": result.get("is_error", False),
            }

        logger.error(f"MCP 工具执行失败: {name}, 错误: {result.get('error', 'Unknown error')}")
        self.console.print("[bold red]❌ MCP 工具执行失败[/bold red]")
        self.console.print(f"[red]错误:[/red] {result.get('error', 'Unknown error')}")
        return {"ok": False, "error": result.get("error", "Unknown error")}
