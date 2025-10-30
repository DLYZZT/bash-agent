from __future__ import annotations
from typing import Any, Dict, List, Optional

import tiktoken
from openai import OpenAI

from .config import Config
from .cli import (
    console,
    confirm_execution,
    print_agent_response,
    render_single_query_panel,
    render_startup_panel,
    setup_readline,
    show_token_stats,
)
from .message_manager import MessageManager
from .tool_handler import ToolHandler
from .mcp_client import MCPClientManager
from .logger import StructuredLogger, get_logger


class Agent:
    """Main orchestrator for the Bash Agent runtime."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.console = console
        self.client = OpenAI()

        # 初始化日志系统
        StructuredLogger.setup(config.log_file)
        self.logger = get_logger(__name__)
        self.logger.info(f"Bash Agent 启动，版本信息 - 模型: {config.openai_model}, OS: {config.os_name}")
        self.logger.info(f"工作目录: {config.work_dir}")
        self.logger.info(f"日志文件: {config.log_file}")

        self.encoding = self._load_encoding(config.openai_model)
        self.token_stats: Dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "api_calls": 0,
            "compressions": 0,
        }

        self.mcp_manager = self._init_mcp_manager()
        self.message_manager = MessageManager(
            config,
            self.console,
            self.client,
            self.encoding,
            self.token_stats,
        )
        self.tool_handler = ToolHandler(
            config,
            self.console,
            lambda cmd: confirm_execution(config, cmd),
            self.mcp_manager,
        )

        self.messages: List[Dict[str, Any]] = []
        self._reset_conversation()

    def _load_encoding(self, model: str):
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")

    def _init_mcp_manager(self) -> Optional[MCPClientManager]:
        if not self.config.mcp_config_path.exists():
            self.logger.info("MCP 配置文件不存在，跳过 MCP 连接")
            return None

        manager = MCPClientManager()
        try:
            if manager.connect_from_config_file(str(self.config.mcp_config_path)):
                self.logger.info(f"成功连接到 MCP 服务器，配置文件: {self.config.mcp_config_path}")
                return manager
            self.logger.warning("MCP 服务器连接失败，将只使用本地工具")
            self.console.print("[bold yellow]⚠️  MCP 服务器连接失败，将只使用本地工具[/bold yellow]")
            return None
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"MCP 服务器初始化错误: {exc}", exc_info=True)
            self.console.print(f"[bold yellow]⚠️  MCP 服务器初始化错误: {exc}[/bold yellow]")
            return None

    def _reset_conversation(self) -> None:
        self.messages = [self.message_manager.load_system()]

    def _update_token_stats(self, response) -> None:
        if response.usage:
            self.token_stats["prompt_tokens"] += response.usage.prompt_tokens
            self.token_stats["completion_tokens"] += response.usage.completion_tokens
            self.token_stats["total_tokens"] += response.usage.total_tokens
            self.token_stats["api_calls"] += 1

    def show_token_stats(self) -> None:
        show_token_stats(self.config, self.message_manager, self.token_stats, self.messages)

    def reset_token_stats(self) -> None:
        for key in self.token_stats:
            self.token_stats[key] = 0

    def _show_help(self) -> None:
        """显示帮助信息"""
        help_text = """
[bold cyan]📖 Bash Agent 帮助[/bold cyan]

[bold yellow]可用命令：[/bold yellow]
  [cyan]/help[/cyan]      - 显示此帮助信息
  [cyan]/stats[/cyan]     - 显示 Token 使用统计
  [cyan]/clear[/cyan]     - 清空对话历史和 Token 统计
  [cyan]/compress[/cyan]  - 手动压缩消息历史
  [cyan]/exit[/cyan]      - 退出程序（或使用 quit）
  [cyan]Ctrl+L[/cyan]     - 清屏

[bold yellow]使用说明：[/bold yellow]
  • 输入自然语言指令，Agent 会生成并执行相应的 Shell 命令
  • 工作目录：[cyan]{work_dir}[/cyan]
  • 操作系统：[cyan]{os_name}[/cyan]
  • Shell 类型：[cyan]{shell_type}[/cyan]

[bold yellow]MCP 集成：[/bold yellow]
  • MCP 状态：[cyan]{mcp_status}[/cyan]
{mcp_details}
"""
        mcp_status, mcp_details = self._collect_mcp_info()

        # 格式化 MCP 详情
        if mcp_details:
            mcp_details_formatted = mcp_details
        else:
            mcp_details_formatted = ""

        formatted_help = help_text.format(
            work_dir=self.config.work_dir,
            os_name=self.config.os_name,
            shell_type=self.config.shell_type,
            mcp_status=mcp_status,
            mcp_details=mcp_details_formatted,
        )
        self.console.print(formatted_help)

    def _collect_mcp_info(self) -> tuple[str, str]:
        if not self.mcp_manager or not self.mcp_manager.is_connected():
            return "未连接", ""

        servers_info = self.mcp_manager.get_servers_info()
        tools_count = len(self.mcp_manager.get_tools_for_openai())
        detail_lines = [f"[cyan]MCP 工具数:[/cyan] {tools_count}"]
        for server_name, info in servers_info.items():
            detail_lines.append(f"[dim]  • {server_name}: {len(info['tools'])} 个工具[/dim]")

        details = "\n".join(detail_lines) + "\n" if detail_lines else ""
        status = f"已连接 ({len(servers_info)} 个服务器)"
        return status, details

    def _call_model(self):
        self.logger.debug(f"调用 OpenAI API，模型: {self.config.openai_model}")
        response = self.client.chat.completions.create(
            model=self.config.openai_model,
            messages=self.messages,
            tools=self.tool_handler.get_tools(),
            tool_choice="auto",
            temperature=float(self.config.model_temperature),
        )
        self._update_token_stats(response)
        self.logger.debug(f"API 调用完成，使用 tokens: {response.usage.total_tokens if response.usage else 0}")
        return response

    def _handle_user_turn(self, user_input: str) -> None:
        self.logger.info(f"用户输入: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
        self.messages.append({"role": "user", "content": user_input})

        while True:
            self.messages = self.message_manager.compress_if_needed(self.messages)
            response = self._call_model()
            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            if not tool_calls:
                self.logger.info(f"Agent 响应（无工具调用）: {(message.content or '')[:100]}{'...' if len(message.content or '') > 100 else ''}")
                print_agent_response(message.content or "")
                break

            self.logger.info(f"Agent 请求调用 {len(tool_calls)} 个工具")
            self.messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": self.message_manager.serialize_tool_calls(tool_calls),
                }
            )

            self.tool_handler.handle_tool_calls(self.messages, tool_calls)

    def run(self, argv: List[str]) -> None:
        """Entry point used by main.py."""
        setup_readline()

        mcp_status, mcp_details = self._collect_mcp_info()
        render_startup_panel(self.config, mcp_status, mcp_details)

        if len(argv) > 1:
            user_query = " ".join(argv[1:])
            render_single_query_panel(user_query)
            self._handle_user_turn(user_query)
            self.show_token_stats()
            return

        self._repl_loop()

    def _repl_loop(self) -> None:
        self.logger.info("进入交互式 REPL 模式")
        while True:
            try:
                user_input = input("\033[1;36m👤 User:\033[0m ").strip()
            except (EOFError, KeyboardInterrupt):
                self.logger.info("用户中断，退出程序")
                self.console.print("\n[bold yellow]👋 再见![/bold yellow]")
                self.show_token_stats()
                break

            if user_input.lower() in ("/exit", "quit"):
                self.logger.info("用户执行退出命令")
                self.console.print("[bold yellow]👋 再见![/bold yellow]")
                self.show_token_stats()
                break

            if user_input.lower() == "/help":
                self.logger.debug("用户查看帮助信息")
                self._show_help()
                continue

            if user_input.lower() == "/clear":
                self.logger.info("用户执行清空对话命令")
                self.show_token_stats()
                self._reset_conversation()
                self.reset_token_stats()
                self.console.print("[bold green]✨ 对话历史已清空，Token 统计已重置[/bold green]")
                continue

            if user_input.lower() == "/stats":
                self.logger.debug("用户查看统计信息")
                self.show_token_stats()
                continue

            if user_input.lower() == "/compress":
                self.logger.info("用户手动触发消息压缩")
                if len(self.messages) <= 1:
                    self.console.print("[bold yellow]⚠️  消息历史为空，无需压缩[/bold yellow]")
                else:
                    self.messages = self.message_manager.manual_compress(self.messages)
                continue

            self._handle_user_turn(user_input)

    def shutdown(self) -> None:
        self.logger.info("开始清理资源")
        if self.mcp_manager:
            try:
                self.mcp_manager.cleanup()
                self.logger.info("MCP 连接已清理")
            except Exception as e:
                self.logger.error(f"清理 MCP 连接时出错: {e}")
        self.logger.info("Bash Agent 正常关闭")
