from dataclasses import dataclass
import os, json, shlex, subprocess, sys, time, pathlib
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Missing OPENAI_API_KEY. Put it in .env or your environment.")
    sys.exit(1)

WORK_DIR = os.getenv("WORK_DIR", "./work")
print(f"Using WORK_DIR: {WORK_DIR}")
CONFIRM_BEFORE_EXEC = os.getenv("CONFIRM_BEFORE_EXEC", "yes").lower() == "yes"
pathlib.Path(WORK_DIR).mkdir(parents=True, exist_ok=True)

client = OpenAI()


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
    # 写根目录或越界：粗略防护
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
        proc = subprocess.run(
            command,
            cwd=WORK_DIR,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=os.environ.copy(),
        )
        return BashResult(proc.stdout, proc.stderr, proc.returncode, ran=True)
    except subprocess.TimeoutExpired:
        return BashResult("", f"timeout > {timeout_s}s", 124, ran=False, reason="timeout")
    except Exception as e:
        return BashResult("", f"exec error: {e}", 1, ran=False, reason="exception")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash_exec",
            "description": f"Execute a bash command inside the isolated working directory: {WORK_DIR}",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command string to execute"},
                    "timeout_s": {"type": "integer", "description": "Timeout seconds (default 30)", "minimum": 1},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    }
]

def call_model(messages, tool_choice="auto"):
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice=tool_choice,
        temperature=0.2,
    )


def load_system():
    sys_path = pathlib.Path(__file__).parent / "prompts" / "system.md"
    text = sys_path.read_text(encoding="utf-8")
    text = text.replace("${WORK_DIR}", str(pathlib.Path(WORK_DIR).resolve()))
    text = text.replace("${NOW_ISO}", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return {"role": "system", "content": text}

def confirm(cmd: str) -> bool:
    if not CONFIRM_BEFORE_EXEC:
        return True
    print(f"\nAbout to execute:\n  {cmd}\nProceed? [y/N] ", end="", flush=True)
    ans = sys.stdin.readline().strip().lower()
    return ans in ("y", "yes")
def tool_loop(user_input: str):
    messages = [load_system(), {"role": "user", "content": user_input}]
    while True:
        resp = call_model(messages)
        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            print(f"\nAssistant:\n{msg.content or ''}")
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
                        result = run_bash(command, timeout_s=timeout_s)
                    else:
                        result = BashResult("", "user declined", 1, ran=False, reason="declined")
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
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps({"ok": False, "error": "unknown tool"}, ensure_ascii=False),
                })

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
        tool_loop(user_query)
    else:
        print("Bash Agent. Type your goal or `exit` to quit.")
        while True:
            try:
                user_input = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break
            if user_input.lower() in ("exit", "quit"):
                print("Bye.")
                break
            tool_loop(user_input)