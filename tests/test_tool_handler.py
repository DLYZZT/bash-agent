import json
from types import SimpleNamespace

from rich.console import Console

from src.config import Config
from src.security import BashResult
from src.tool_handler import ToolHandler


def make_config(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    log_file = tmp_path / "test.log"
    return Config(
        openai_api_key="test",
        openai_model="gpt-test",
        model_temperature=0.0,
        work_dir=work_dir,
        confirm_before_exec=True,
        mcp_config_path=tmp_path / "mcp.json",
        max_context_tokens=1000,
        keep_recent_messages=5,
        os_name="Linux",
        shell_type="bash",
        project_root=tmp_path,
        log_file=log_file,
    )


def test_tool_handler_runs_bash_exec(monkeypatch, tmp_path):
    config = make_config(tmp_path)
    console = Console(record=True)

    result = BashResult(stdout="done\n", stderr="", exit_code=0, ran=True, reason="")
    monkeypatch.setattr(
        "src.tool_handler.run_bash",
        lambda command, config, timeout_s=30: result,
    )

    handler = ToolHandler(config, console, confirm=lambda _: True, mcp_manager=None)
    messages = []
    tool_call = SimpleNamespace(
        id="1",
        function=SimpleNamespace(name="bash_exec", arguments=json.dumps({"command": "echo 1"})),
    )

    handler.handle_tool_calls(messages, [tool_call])

    assert messages
    payload = json.loads(messages[-1]["content"])
    assert payload["ok"] is True
    assert payload["stdout"] == "done\n"


def test_tool_handler_reports_missing_mcp(tmp_path):
    config = make_config(tmp_path)
    console = Console(record=True)
    handler = ToolHandler(config, console, confirm=lambda _: True, mcp_manager=None)

    messages = []
    tool_call = SimpleNamespace(
        id="tool-1",
        function=SimpleNamespace(name="mcp_server_tool", arguments="{}"),
    )

    handler.handle_tool_calls(messages, [tool_call])

    payload = json.loads(messages[-1]["content"])
    assert payload["ok"] is False
    assert "未连接" in payload["error"]


def test_tool_list_includes_mcp_tools_when_available(tmp_path):
    class FakeMCP:
        def __init__(self):
            self.tools = [
                {"type": "function", "function": {"name": "mcp_demo_tool", "description": "Demo", "parameters": {}}}
            ]

        def is_connected(self):
            return True

        def get_tools_for_openai(self):
            return self.tools

    config = make_config(tmp_path)
    console = Console(record=True)
    handler = ToolHandler(config, console, confirm=lambda _: True, mcp_manager=FakeMCP())

    tools = handler.get_tools()
    assert any(tool["function"]["name"] == "mcp_demo_tool" for tool in tools if tool["type"] == "function")
