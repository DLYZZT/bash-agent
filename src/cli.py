from __future__ import annotations

import readline
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax

from .config import Config
from .message_manager import MessageManager

console = Console()


def setup_readline() -> None:
    """Enable readline shortcuts (currently Ctrl+L to clear)."""
    try:
        readline.parse_and_bind(r'"\C-l": clear-screen')
    except Exception: # windows use pyreadline
        import pyreadline
        pyreadline.parse_and_bind(r'"\C-l": clear-screen')

def confirm_execution(config: Config, command: str) -> bool:
    if not config.confirm_before_exec:
        return True

    console.print(
        Panel(
            Syntax(command, "bash", theme="monokai", line_numbers=False),
            title="[bold yellow]⚠️  即将执行命令[/bold yellow]",
            border_style="yellow",
        )
    )

    try:
        answer = Prompt.ask("是否继续执行", choices=["y", "yes", "n", "no"], default="n").lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        console.print("[bold red]输入被中断，默认不执行命令[/bold red]")
        return False


def show_token_stats(
    config: Config,
    message_manager: MessageManager,
    token_stats: Dict[str, Any],
    messages: List[Dict[str, Any]],
) -> None:
    if token_stats["api_calls"] == 0:
        return

    cost_per_1k_prompt = 0.00015
    cost_per_1k_completion = 0.0006

    prompt_cost = (token_stats["prompt_tokens"] / 1000) * cost_per_1k_prompt
    completion_cost = (token_stats["completion_tokens"] / 1000) * cost_per_1k_completion
    total_cost = prompt_cost + completion_cost

    stats_text = (
        f"[bold cyan]📊 Token 使用统计[/bold cyan]\n\n"
        f"[cyan]API 调用次数:[/cyan] {token_stats['api_calls']}\n"
        f"[cyan]输入 Tokens:[/cyan] {token_stats['prompt_tokens']:,}\n"
        f"[cyan]输出 Tokens:[/cyan] {token_stats['completion_tokens']:,}\n"
        f"[cyan]总计 Tokens:[/cyan] {token_stats['total_tokens']:,}\n"
        f"[cyan]预估成本:[/cyan] ${total_cost:.6f} USD"
    )

    if token_stats["compressions"] > 0:
        stats_text += f"\n[cyan]消息压缩次数:[/cyan] {token_stats['compressions']}"

    current_tokens = message_manager.count_message_tokens(messages)
    stats_text += f"\n[cyan]当前消息 Tokens:[/cyan] {current_tokens:,} / {config.max_context_tokens:,}"

    if config.openai_model != "gpt-4o-mini":
        stats_text += f"\n[dim]注意: 成本按 gpt-4o-mini 价格估算，实际使用模型: {config.openai_model}[/dim]"

    console.print(
        Panel.fit(
            stats_text,
            title="[bold blue]会话统计[/bold blue]",
            border_style="blue",
        )
    )


def render_startup_panel(
    config: Config,
    mcp_status: str,
    mcp_details: str,
) -> None:
    startup_info = (
        f"[bold green]🚀 Bash Agent 启动成功![/bold green]\n\n"
        f"[cyan]模型:[/cyan] {config.openai_model}\n"
        f"[cyan]操作系统:[/cyan] {config.os_name}\n"
        f"[cyan]Shell类型:[/cyan] {config.shell_type}\n"
        f"[cyan]工作目录:[/cyan] {config.work_dir}\n"
        f"[cyan]确认执行:[/cyan] {'是' if config.confirm_before_exec else '否'}\n"
        f"[cyan]MCP 状态:[/cyan] {mcp_status}\n"
        + mcp_details
    )

    startup_info += (
        "\n[dim]输入 [bold red]/exit[/bold red] 退出 | 输入 [bold yellow]/clear[/bold yellow] 清空对话\n"
        "输入 [bold cyan]/stats[/bold cyan] 查看统计 | 输入 [bold magenta]/compress[/bold magenta] 手动压缩 | "
        "按 [bold green]Ctrl+L[/bold green] 清屏[/dim]"
    )

    console.print(
        Panel.fit(
            startup_info,
            title="[bold blue]Bash Agent[/bold blue]",
            border_style="blue",
        )
    )


def render_single_query_panel(user_query: str) -> None:
    console.print(
        Panel(
            f"[bold cyan]用户查询:[/bold cyan] {user_query}",
            title="[bold blue]🎯 任务[/bold blue]",
            border_style="blue",
        )
    )


def print_agent_response(content: Optional[str]) -> None:
    console.print(f"[bold green]🤖 Agent:[/bold green] {content or ''}")
