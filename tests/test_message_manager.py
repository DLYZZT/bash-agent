from types import SimpleNamespace

from rich.console import Console

from src.config import Config
from src.message_manager import MessageManager


class FakeEncoding:
    def encode(self, text: str) -> list[int]:
        text = text or ""
        return list(range(len(text)))


class FakeClient:
    class _Chat:
        class _Completions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="summary"))],
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                )

        def __init__(self):
            self.completions = FakeClient._Chat._Completions()

    def __init__(self):
        self.chat = FakeClient._Chat()


def make_manager(tmp_path, keep_recent=2, max_tokens=50):
    project_root = tmp_path / "proj"
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text("system ${WORK_DIR} ${NOW_ISO} ${OS_NAME} ${SHELL_TYPE}", encoding="utf-8")
    (prompts_dir / "summary.md").write_text("summary prompt", encoding="utf-8")

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    config = Config(
        openai_api_key="key",
        openai_model="model",
        model_temperature=0.0,
        work_dir=work_dir,
        confirm_before_exec=False,
        mcp_config_path=tmp_path / "mcp.json",
        max_context_tokens=max_tokens,
        keep_recent_messages=keep_recent,
        os_name="Linux",
        shell_type="bash",
        project_root=project_root,
    )

    console = Console(record=True)
    client = FakeClient()
    encoding = FakeEncoding()
    token_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "api_calls": 0, "compressions": 0}
    return MessageManager(config, console, client, encoding, token_stats)


def test_count_message_tokens(tmp_path):
    manager = make_manager(tmp_path)
    messages = [{"role": "user", "content": "hi"}]
    assert manager.count_message_tokens(messages) == 12


def test_find_safe_split_keeps_tool_pairs(tmp_path):
    manager = make_manager(tmp_path, keep_recent=1)
    messages = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "a"}}, {"function": {"name": "b"}}]},
        {"role": "tool", "name": "call-1"},
        {"role": "tool", "name": "call-2"},
        {"role": "user", "content": "latest"},
    ]

    old_msgs, recent_msgs = manager._find_safe_split_point(messages, keep_count=1)
    assert len(recent_msgs) == 1
    assert recent_msgs[0]["role"] == "user"
    assert len(old_msgs) == 3
    assert old_msgs[0]["role"] == "assistant"


def test_compress_if_needed_triggers_force(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, max_tokens=10)
    messages = [{"role": "user", "content": "hi"}]

    monkeypatch.setattr(manager, "count_message_tokens", lambda _: 999)

    captured = {}

    def fake_compress(msgs, force):
        captured["force"] = force
        return ["compressed"]

    monkeypatch.setattr(manager, "_do_compress_messages", fake_compress)
    result = manager.compress_if_needed(messages)
    assert result == ["compressed"]
    assert captured["force"] is True


def test_manual_compress_uses_do_compress(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    messages = [{"role": "user", "content": "hi"}]

    monkeypatch.setattr(manager, "_do_compress_messages", lambda msgs, force: ["manual", force])
    result = manager.manual_compress(messages)
    assert result == ["manual", False]


def test_serialize_tool_calls(tmp_path):
    manager = make_manager(tmp_path)
    tool_calls = [
        SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(name="bash_exec", arguments='{"command": "ls"}'),
        )
    ]

    serialized = manager.serialize_tool_calls(tool_calls)
    assert serialized[0]["id"] == "call-1"
    assert serialized[0]["function"]["name"] == "bash_exec"
