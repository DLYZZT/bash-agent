from __future__ import annotations

import os
import pathlib
import shlex
import subprocess
from dataclasses import dataclass

from .config import Config
from .logger import get_logger

logger = get_logger(__name__)


DENY_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    ":(){:|:&};:",
]

DANGEROUS_TOKENS = [
    "sudo",
    "mkfs",
    "shutdown",
    "reboot",
    "dd",
    "iptables",
    "chmod 777 -R",
    "chown -R /",
]


@dataclass
class BashResult:
    stdout: str
    stderr: str
    exit_code: int
    ran: bool
    reason: str = ""


def is_obviously_dangerous(command: str) -> bool:
    lowered = command.strip().lower()
    if any(pattern in lowered for pattern in DENY_PATTERNS):
        logger.warning(f"检测到危险命令模式: {command[:50]}")
        return True
    if any(token in lowered for token in DANGEROUS_TOKENS):
        logger.warning(f"检测到危险命令 token: {command[:50]}")
        return True
    if " /etc" in lowered or " /root" in lowered:
        logger.warning(f"检测到访问敏感目录: {command[:50]}")
        return True
    return False


def is_outside_workdir(command: str, work_dir: pathlib.Path) -> bool:
    tokens = shlex.split(command) if command.strip() else []
    for token in tokens:
        if token.startswith("/"):
            return True
        if ".." in pathlib.PurePosixPath(token).parts:
            return True
    return False


def run_bash(command: str, config: Config, timeout_s: int = 30) -> BashResult:
    logger.info(f"准备执行命令: {command[:100]}{'...' if len(command) > 100 else ''}")

    if not command.strip():
        logger.warning("命令为空，拒绝执行")
        return BashResult("", "empty command", 1, ran=False, reason="empty")

    if is_outside_workdir(command, config.work_dir):
        logger.warning(f"命令尝试访问工作目录外的路径: {command[:50]}")
        return BashResult(
            "",
            f"blocked: path outside WORK_DIR ({config.work_dir})",
            1,
            ran=False,
            reason="path_outside",
        )

    if is_obviously_dangerous(command):
        logger.error(f"命令被安全检查拦截: {command[:50]}")
        return BashResult("", "blocked: dangerous command", 1, ran=False, reason="dangerous")

    try:
        logger.debug(f"在目录 {config.work_dir} 中执行命令，超时设置: {timeout_s}s")
        if config.shell_type == "cmd":
            proc = subprocess.run(
                command,
                cwd=config.work_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=os.environ.copy(),
                executable="cmd.exe",
            )
        else:
            proc = subprocess.run(
                command,
                cwd=config.work_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=os.environ.copy(),
                executable="/bin/bash",
            )

        result = BashResult(proc.stdout, proc.stderr, proc.returncode, ran=True)
        if result.exit_code == 0:
            logger.info(f"命令执行成功，退出码: {result.exit_code}")
        else:
            logger.warning(f"命令执行失败，退出码: {result.exit_code}, stderr: {proc.stderr[:100]}")
        return result

    except subprocess.TimeoutExpired:
        logger.error(f"命令执行超时 (>{timeout_s}s): {command[:50]}")
        return BashResult("", f"timeout > {timeout_s}s", 124, ran=False, reason="timeout")
    except Exception as e:
        logger.error(f"命令执行异常: {e}", exc_info=True)
        return BashResult("", f"exec error: {e}", 1, ran=False, reason="exception")
