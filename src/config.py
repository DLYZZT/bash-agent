from __future__ import annotations

import os
import pathlib
import platform
from dataclasses import dataclass
from typing import Tuple

from dotenv import load_dotenv
from rich.console import Console


@dataclass(frozen=True)
class Config:
    openai_api_key: str
    openai_model: str
    model_temperature: float
    work_dir: pathlib.Path
    confirm_before_exec: bool
    mcp_config_path: pathlib.Path
    max_context_tokens: int
    keep_recent_messages: int
    os_name: str
    shell_type: str
    project_root: pathlib.Path
    log_file: pathlib.Path


def _get_os_info() -> Tuple[str, str]:
    system = platform.system()
    if system == "Darwin":
        return "macOS", "bash"
    if system == "Linux":
        return "Linux", "bash"
    if system == "Windows":
        return "Windows", "cmd"
    return system, "bash"


def load_config(console: Console) -> Config:
    load_dotenv()
    project_root = pathlib.Path(__file__).resolve().parents[1]

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("[bold red]❌ 错误: 缺少 OPENAI_API_KEY[/bold red]")
        console.print("请在 .env 文件或环境变量中设置 OPENAI_API_KEY")
        raise SystemExit(1)

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    temperature = float(os.getenv("MODEL_TEMPERATURE", "0.2"))
    work_dir = pathlib.Path(os.getenv("WORK_DIR", "./work")).resolve()
    confirm_before_exec = os.getenv("CONFIRM_BEFORE_EXEC", "yes").lower() == "yes"
    mcp_config_path = pathlib.Path(os.getenv("MCP_CONFIG_PATH", "./mcp_config.json")).resolve()
    max_context_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", "100000"))
    keep_recent_messages = int(os.getenv("KEEP_RECENT_MESSAGES", "10"))

    work_dir.mkdir(parents=True, exist_ok=True)

    os_name, shell_type = _get_os_info()

    home_dir = pathlib.Path.home()
    log_dir = home_dir / ".bash-agent"
    log_file = log_dir / "bash-agent.log"
    log_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        openai_api_key=api_key,
        openai_model=model,
        model_temperature=temperature,
        work_dir=work_dir,
        confirm_before_exec=confirm_before_exec,
        mcp_config_path=mcp_config_path,
        max_context_tokens=max_context_tokens,
        keep_recent_messages=keep_recent_messages,
        os_name=os_name,
        shell_type=shell_type,
        project_root=project_root,
        log_file=log_file,
    )
