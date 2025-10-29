from dataclasses import dataclass
import os, json, shlex, subprocess, sys, time, pathlib, platform, readline
from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.status import Status
from rich.syntax import Syntax
from mcp_client import MCPClientManager

console = Console()

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    console.print("[bold red]❌ 错误: 缺少 OPENAI_API_KEY[/bold red]")
    console.print("请在 .env 文件或环境变量中设置 OPENAI_API_KEY")
    sys.exit(1)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MODEL_TEMPERATURE = os.getenv("MODEL_TEMPERATURE", 0.2)
WORK_DIR = os.getenv("WORK_DIR", "./work")
CONFIRM_BEFORE_EXEC = os.getenv("CONFIRM_BEFORE_EXEC", "yes").lower() == "yes"
MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "./mcp_config.json")
pathlib.Path(WORK_DIR).mkdir(parents=True, exist_ok=True)

mcp_manager = None
if pathlib.Path(MCP_CONFIG_PATH).exists():
    mcp_manager = MCPClientManager()

def get_os_info():
    system = platform.system()
    if system == "Darwin":
        return "macOS", "bash"
    elif system == "Linux":
        return "Linux", "bash"
    elif system == "Windows":
        return "Windows", "cmd"
    else:
        return system, "bash"

OS_NAME, SHELL_TYPE = get_os_info()

client = OpenAI()
messages = []

# Token 使用统计
token_stats = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "api_calls": 0
}

if mcp_manager:
    try:
        if mcp_manager.connect_from_config_file(MCP_CONFIG_PATH):
            pass
        else:
            console.print("[bold yellow]⚠️  MCP 服务器连接失败，将只使用本地工具[/bold yellow]")
            mcp_manager = None
    except Exception as e:
        console.print(f"[bold yellow]⚠️  MCP 服务器初始化错误: {e}[/bold yellow]")
        mcp_manager = None

DENY_PATTERNS = [
    "rm -rf /", "rm -rf /*", ":(){:|:&};:",
]
DANGEROUS_TOKENS = ["sudo", "mkfs", "shutdown", "reboot", "dd", "iptables", "chmod 777 -R", "chown -R /"]
def is_obviously_dangerous(cmd: str) -> bool:
    low = cmd.strip().lower()
    if any(p in low for p in [p for p in DENY_PATTERNS]):
        return True
    if any(tok in low for tok in DANGEROUS_TOKENS):
        return True

    if " /etc" in low or " /root" in low:
        return True
    return False

def is_outside_workdir(target: str) -> bool:
    toks = shlex.split(target) if target.strip() else []
    for t in toks:
        if t.startswith("/"):
            return True
        if ".." in pathlib.PurePosixPath(t).parts:
            return True
    return False

@dataclass
class BashResult:
    stdout: str
    stderr: str
    exit_code: int
    ran: bool
    reason: str = ""

def run_bash(command: str, timeout_s: int = 30) -> BashResult:
    if not command.strip():
        return BashResult("", "empty command", 1, ran=False, reason="empty")
    if is_outside_workdir(command):
        return BashResult("", f"blocked: path outside WORK_DIR ({WORK_DIR})", 1, ran=False, reason="path_outside")
    if is_obviously_dangerous(command):
        return BashResult("", "blocked: dangerous command", 1, ran=False, reason="dangerous")

    try:
        if SHELL_TYPE == "cmd":
            proc = subprocess.run(
                command,
                cwd=WORK_DIR,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=os.environ.copy(),
                executable="cmd.exe"
            )
        else:
            proc = subprocess.run(
                command,
                cwd=WORK_DIR,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=os.environ.copy(),
                executable="/bin/bash"
            )
        return BashResult(proc.stdout, proc.stderr, proc.returncode, ran=True)
    except subprocess.TimeoutExpired:
        return BashResult("", f"timeout > {timeout_s}s", 124, ran=False, reason="timeout")
    except Exception as e:
        return BashResult("", f"exec error: {e}", 1, ran=False, reason="exception")

def get_available_tools():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "bash_exec",
                "description": f"Execute a shell command inside the isolated working directory: {WORK_DIR}. Current OS: {OS_NAME}, Shell: {SHELL_TYPE}. Use appropriate commands for the OS (e.g., 'ls' for macOS/Linux, 'dir' for Windows).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": f"The shell command string to execute (using {SHELL_TYPE})"},
                        "timeout_s": {"type": "integer", "description": "Timeout seconds (default 30)", "minimum": 1},
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
            },
        }
    ]
    
    # 添加 MCP 工具
    if mcp_manager and mcp_manager.is_connected():
        mcp_tools = mcp_manager.get_tools_for_openai()
        tools.extend(mcp_tools)
    
    return tools

TOOLS = get_available_tools()

def call_model(messages, tool_choice="auto"):
    global token_stats
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice=tool_choice,
        temperature=float(MODEL_TEMPERATURE),
    )
    
    # 记录 token 使用情况
    if response.usage:
        token_stats["prompt_tokens"] += response.usage.prompt_tokens
        token_stats["completion_tokens"] += response.usage.completion_tokens
        token_stats["total_tokens"] += response.usage.total_tokens
        token_stats["api_calls"] += 1
    
    return response

def load_system():
    sys_path = pathlib.Path(__file__).parent / "prompts" / "system.md"
    text = sys_path.read_text(encoding="utf-8")
    text = text.replace("${WORK_DIR}", str(pathlib.Path(WORK_DIR).resolve()))
    text = text.replace("${NOW_ISO}", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    text = text.replace("${OS_NAME}", OS_NAME)
    text = text.replace("${SHELL_TYPE}", SHELL_TYPE)
    return {"role": "system", "content": text}

def setup_readline():
    try:
        # 绑定 Ctrl+L 到清屏函数
        readline.parse_and_bind(r'"\C-l": clear-screen')
    except Exception:
        pass

def show_token_stats():
    """显示 Token 使用统计"""
    global token_stats
    
    if token_stats["api_calls"] == 0:
        return
    
    # 计算成本
    cost_per_1k_prompt = 0.00015  # $0.15 per 1M tokens
    cost_per_1k_completion = 0.0006  # $0.60 per 1M tokens
    
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
    
    if OPENAI_MODEL != "gpt-4o-mini":
        stats_text += f"\n[dim]注意: 成本按 gpt-4o-mini 价格估算，实际使用模型: {OPENAI_MODEL}[/dim]"
    
    console.print(Panel.fit(
        stats_text,
        title="[bold blue]会话统计[/bold blue]",
        border_style="blue"
    ))

def confirm(cmd: str) -> bool:
    if not CONFIRM_BEFORE_EXEC:
        return True
    
    console.print(Panel(
        Syntax(cmd, "bash", theme="monokai", line_numbers=False),
        title="[bold yellow]⚠️  即将执行命令[/bold yellow]",
        border_style="yellow"
    ))
    
    try:
        ans = Prompt.ask("是否继续执行", choices=["y", "yes", "n", "no"], default="n").lower()
        return ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        console.print("[bold red]输入被中断，默认不执行命令[/bold red]")
        return False

def tool_loop(user_input: str):
    global messages, TOOLS
    messages.append({"role": "user", "content": user_input})
    
    TOOLS = get_available_tools()
    
    while True:
        resp = call_model(messages)
        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            console.print(f"[bold green]🤖 Agent:[/bold green] {msg.content or ''}")
            break

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")

            if name == "bash_exec":
                command = args.get("command", "")
                timeout_s = int(args.get("timeout_s", 30))

                if is_obviously_dangerous(command):
                    payload = {
                        "ok": False, "ran": False, "reason": "dangerous_command_blocked",
                        "stdout": "", "stderr": "blocked by guard", "exit_code": 1
                    }
                elif is_outside_workdir(command):
                    payload = {
                        "ok": False, "ran": False, "reason": "outside_workdir_blocked",
                        "stdout": "", "stderr": f"must stay inside {WORK_DIR}", "exit_code": 1
                    }
                else:
                    if confirm(command):
                        with Status("[bold blue]执行命令中...", spinner="dots"):
                            result = run_bash(command, timeout_s=timeout_s)

                        if result.exit_code == 0 and result.ran:
                            console.print("[bold green]✅ 命令执行成功[/bold green]")
                        else:
                            console.print("[bold red]❌ 命令执行失败[/bold red]")
                        
                        if result.stdout:
                            console.print(f"[cyan]输出:[/cyan] {result.stdout}")
                        if result.stderr:
                            console.print(f"[red]错误:[/red] {result.stderr}")
                        if result.reason:
                            console.print(f"[yellow]原因:[/yellow] {result.reason}")
                    else:
                        result = BashResult("", "user declined", 1, ran=False, reason="declined")
                        console.print("[bold yellow]⏸️  用户取消了命令执行[/bold yellow]")
                    
                    payload = {
                        "ok": result.exit_code == 0 and result.ran,
                        "ran": result.ran,
                        "reason": result.reason,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_code
                    }

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(payload, ensure_ascii=False),
                })
            
            elif name.startswith("mcp_"):
                if mcp_manager and mcp_manager.is_connected():
                    # 解析服务器名称和工具名称
                    # 格式: mcp_<server_name>_<tool_name>
                    parts = name[4:].split("_", 1)
                    if len(parts) == 2:
                        server_name, tool_name = parts
                        console.print(f"[bold blue]🔧 调用 MCP 工具: [{server_name}] {tool_name}[/bold blue]")
                    else:
                        console.print(f"[bold blue]🔧 调用 MCP 工具: {name}[/bold blue]")
                    
                    with Status(f"[bold blue]执行 MCP 工具...", spinner="dots"):
                        result = mcp_manager.call_tool(name, args)
                    
                    if result.get("success"):
                        console.print(f"[bold green]✅ MCP 工具执行成功[/bold green]")
                        
                        content_items = result.get("content", [])
                        if content_items:
                            for item in content_items:
                                if item.get("type") == "text":
                                    text = item.get("text", "")
                                    if text:
                                        pass
                                        # console.print(f"[cyan]返回:[/cyan] {text[:500]}{'...' if len(text) > 500 else ''}")
                        
                        payload = {
                            "ok": True,
                            "content": result.get("content", []),
                            "is_error": result.get("is_error", False)
                        }
                    else:
                        console.print(f"[bold red]❌ MCP 工具执行失败[/bold red]")
                        console.print(f"[red]错误:[/red] {result.get('error', 'Unknown error')}")
                        payload = {
                            "ok": False,
                            "error": result.get("error", "Unknown error")
                        }
                else:
                    payload = {
                        "ok": False,
                        "error": "MCP 客户端未连接"
                    }
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(payload, ensure_ascii=False),
                })

            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps({"ok": False, "error": "unknown tool"}, ensure_ascii=False),
                })

if __name__ == "__main__":
    try:
        setup_readline()
        
        messages.append(load_system())
        mcp_status = "未连接"
        mcp_details = ""
        
        if mcp_manager and mcp_manager.is_connected():
            servers_info = mcp_manager.get_servers_info()
            mcp_status = f"已连接 ({len(servers_info)} 个服务器)"
            tools_count = len(mcp_manager.get_tools_for_openai())
            mcp_details = f"[cyan]MCP 工具数:[/cyan] {tools_count}\n"
            for server_name, info in servers_info.items():
                mcp_details += f"[dim]  • {server_name}: {len(info['tools'])} 个工具[/dim]\n"
        
        startup_info = (
            f"[bold green]🚀 Bash Agent 启动成功![/bold green]\n\n"
            f"[cyan]模型:[/cyan] {OPENAI_MODEL}\n"
            f"[cyan]操作系统:[/cyan] {OS_NAME}\n"
            f"[cyan]Shell类型:[/cyan] {SHELL_TYPE}\n"
            f"[cyan]工作目录:[/cyan] {WORK_DIR}\n"
            f"[cyan]确认执行:[/cyan] {'是' if CONFIRM_BEFORE_EXEC else '否'}\n"
            f"[cyan]MCP 状态:[/cyan] {mcp_status}\n"
            + mcp_details
        )
        
        startup_info += "\n[dim]输入 [bold red]/exit[/bold red] 退出 | 输入 [bold yellow]/clear[/bold yellow] 清空对话历史 | 输入 [bold cyan]/stats[/bold cyan] 查看统计 | 按 [bold green]Ctrl+L[/bold green] 清屏[/dim]"
        
        console.print(Panel.fit(
            startup_info,
            title="[bold blue]Bash Agent[/bold blue]",
            border_style="blue"
        ))
        
        if len(sys.argv) > 1:
            user_query = " ".join(sys.argv[1:])
            console.print(Panel(
                f"[bold cyan]用户查询:[/bold cyan] {user_query}",
                title="[bold blue]🎯 任务[/bold blue]",
                border_style="blue"
            ))
            tool_loop(user_query)
            show_token_stats()
        else:
            
            while True:
                try:
                    user_input = input("\033[1;36m👤 User:\033[0m ").strip()
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[bold yellow]👋 再见![/bold yellow]")
                    show_token_stats()
                    break
                if user_input.lower() in ("/exit", "quit"):
                    console.print("[bold yellow]👋 再见![/bold yellow]")
                    show_token_stats()
                    break
                if user_input.lower() == "/clear":
                    show_token_stats()
                    messages.clear()
                    messages.append(load_system())

                    token_stats["prompt_tokens"] = 0
                    token_stats["completion_tokens"] = 0
                    token_stats["total_tokens"] = 0
                    token_stats["api_calls"] = 0
                    console.print("[bold green]✨ 对话历史已清空，Token 统计已重置[/bold green]")
                    continue
                if user_input.lower() == "/stats":
                    show_token_stats()
                    continue
                tool_loop(user_input)
    
    finally:
        if mcp_manager:
            try:
                mcp_manager.cleanup()
            except Exception:
                pass