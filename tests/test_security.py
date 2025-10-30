from pathlib import Path

from src.config import Config
from src.security import is_obviously_dangerous, is_outside_workdir, run_bash


def make_config(tmp_path: Path) -> Config:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    return Config(
        openai_api_key="test",
        openai_model="gpt-test",
        model_temperature=0.0,
        work_dir=work_dir,
        confirm_before_exec=False,
        mcp_config_path=tmp_path / "mcp.json",
        max_context_tokens=1000,
        keep_recent_messages=5,
        os_name="Linux",
        shell_type="bash",
        project_root=tmp_path,
    )


def test_is_obviously_dangerous_identifies_risky_commands():
    assert is_obviously_dangerous("rm -rf /")
    assert is_obviously_dangerous("sudo reboot now")
    assert is_obviously_dangerous("ls /root")
    assert not is_obviously_dangerous("echo 'hello world'")


def test_is_outside_workdir_flags_absolute_and_parent_paths(tmp_path):
    work_dir = tmp_path / "sandbox"
    work_dir.mkdir()
    assert is_outside_workdir("/etc/passwd", work_dir)
    assert is_outside_workdir("../secret.txt", work_dir)
    assert not is_outside_workdir("safe.txt", work_dir)


def test_run_bash_blocks_outside_paths(tmp_path):
    config = make_config(tmp_path)
    result = run_bash("cat ../etc/passwd", config)
    assert result.ran is False
    assert result.reason == "path_outside"


def test_run_bash_executes_safe_command(tmp_path):
    config = make_config(tmp_path)
    result = run_bash("echo hello", config)
    assert result.exit_code == 0
    assert result.ran is True
    assert "hello" in result.stdout.strip()
