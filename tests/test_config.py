from rich.console import Console

from src.config import load_config


def test_load_config_reads_environment(monkeypatch, tmp_path):
    work_dir = tmp_path / "work"
    mcp_config = tmp_path / "mcp.json"

    env = {
        "OPENAI_API_KEY": "unit-test-key",
        "OPENAI_MODEL": "gpt-test",
        "MODEL_TEMPERATURE": "0.5",
        "WORK_DIR": str(work_dir),
        "CONFIRM_BEFORE_EXEC": "no",
        "MCP_CONFIG_PATH": str(mcp_config),
        "MAX_CONTEXT_TOKENS": "4096",
        "KEEP_RECENT_MESSAGES": "7",
    }

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    console = Console(record=True)
    config = load_config(console)

    assert config.openai_api_key == "unit-test-key"
    assert config.openai_model == "gpt-test"
    assert config.model_temperature == 0.5
    assert config.work_dir == work_dir.resolve()
    assert config.work_dir.exists()
    assert config.confirm_before_exec is False
    assert config.mcp_config_path == mcp_config.resolve()
    assert config.max_context_tokens == 4096
    assert config.keep_recent_messages == 7
    assert config.project_root.is_dir()
    assert config.shell_type in {"bash", "cmd"}
