from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from openai import OpenAI
from rich.console import Console
from rich.status import Status

from .config import Config


class MessageManager:

    def __init__(
        self,
        config: Config,
        console: Console,
        client: OpenAI,
        encoding,
        token_stats: Dict[str, Any],
    ) -> None:
        self.config = config
        self.console = console
        self.client = client
        self.encoding = encoding
        self.token_stats = token_stats

    def load_system(self) -> Dict[str, str]:
        path = self.config.project_root / "prompts" / "system.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("${WORK_DIR}", str(self.config.work_dir))
        text = text.replace("${NOW_ISO}", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        text = text.replace("${OS_NAME}", self.config.os_name)
        text = text.replace("${SHELL_TYPE}", self.config.shell_type)
        return {"role": "system", "content": text}

    def _load_summary_prompt(self) -> str:
        path = self.config.project_root / "prompts" / "summary.md"
        return path.read_text(encoding="utf-8")

    def count_message_tokens(self, messages: List[Dict[str, Any]]) -> int:
        num_tokens = 0
        for message in messages:
            num_tokens += 4

            if isinstance(message.get("content"), str):
                num_tokens += len(self.encoding.encode(message["content"]))

            num_tokens += len(self.encoding.encode(message.get("role", "")))

            if "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    if "function" in tool_call:
                        num_tokens += len(self.encoding.encode(tool_call["function"].get("name", "")))
                        num_tokens += len(self.encoding.encode(tool_call["function"].get("arguments", "")))

            if "name" in message:
                num_tokens += len(self.encoding.encode(message["name"]))

        return num_tokens + 2

    def _summarize_messages(self, messages_to_summarize: List[Dict[str, Any]]) -> str:
        system_prompt = self._load_summary_prompt()
        history_content = "请总结以下对话历史：\n\n"

        for message in messages_to_summarize:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            if role == "user":
                history_content += f"用户: {content}\n\n"
            elif role == "assistant":
                history_content += f"助手: {content}\n"
                for tool_call in message.get("tool_calls", []):
                    func_name = tool_call.get("function", {}).get("name", "")
                    history_content += f"  [调用工具: {func_name}]\n"
                history_content += "\n"
            elif role == "tool":
                tool_name = message.get("name", "")
                history_content += f"[工具 {tool_name} 返回结果]\n\n"

        try:
            response = self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": history_content},
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            summary = response.choices[0].message.content

            if response.usage:
                self.token_stats["prompt_tokens"] += response.usage.prompt_tokens
                self.token_stats["completion_tokens"] += response.usage.completion_tokens
                self.token_stats["total_tokens"] += response.usage.total_tokens

            return summary
        except Exception as e:
            self.console.print(f"[bold yellow]⚠️  消息总结失败: {e}[/bold yellow]")
            return "（历史消息已压缩，部分上下文可能丢失）"

    def _find_safe_split_point(
        self,
        messages: List[Dict[str, Any]],
        keep_count: int,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if len(messages) <= keep_count:
            return [], messages

        split_index = len(messages) - keep_count

        if split_index < len(messages):
            first_recent = messages[split_index]
            if first_recent.get("role") == "tool":
                i = split_index - 1
                while i >= 0:
                    msg = messages[i]
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        split_index = i
                        break
                    if msg.get("role") != "tool":
                        break
                    i -= 1

        if split_index > 0:
            last_old = messages[split_index - 1]
            if last_old.get("role") == "assistant" and last_old.get("tool_calls"):
                num_tool_calls = len(last_old.get("tool_calls", []))
                tools_found = 0
                i = split_index
                while i < len(messages) and tools_found < num_tool_calls:
                    if messages[i].get("role") == "tool":
                        tools_found += 1
                        i += 1
                    else:
                        break
                if tools_found > 0:
                    split_index = i

        return messages[:split_index], messages[split_index:]

    def _do_compress_messages(
        self,
        messages: List[Dict[str, Any]],
        force: bool,
    ) -> List[Dict[str, Any]]:
        current_tokens = self.count_message_tokens(messages)

        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        non_system_messages = [msg for msg in messages if msg.get("role") != "system"]

        if len(non_system_messages) <= self.config.keep_recent_messages:
            if not force:
                self.console.print(f"[bold yellow]⚠️  消息数量较少（{len(non_system_messages)} 条），无法进一步压缩[/bold yellow]")
                return messages
            adjusted_keep = max(3, len(non_system_messages) // 2)
            old_messages, recent_messages = self._find_safe_split_point(non_system_messages, adjusted_keep)
            self.console.print(
                f"[cyan]调整策略:[/cyan] 保留最近 {len(recent_messages)} 条消息（原计划 {self.config.keep_recent_messages} 条）"
            )
        else:
            old_messages, recent_messages = self._find_safe_split_point(
                non_system_messages,
                self.config.keep_recent_messages,
            )

        if not force:
            if len(old_messages) < 5:
                self.console.print(
                    f"[bold yellow]⚠️  要压缩的消息过少（{len(old_messages)} 条），建议至少有 5 条以上才值得压缩[/bold yellow]"
                )
                self.console.print(
                    f"[dim]提示：可以减小 KEEP_RECENT_MESSAGES 参数（当前为 {self.config.keep_recent_messages}），或等待更多对话后再压缩[/dim]"
                )
                return messages

            old_tokens = self.count_message_tokens(old_messages)
            if old_tokens < 500:
                self.console.print(
                    f"[bold yellow]⚠️  要压缩的消息 token 过少（{old_tokens} tokens），压缩可能不划算[/bold yellow]"
                )
                self.console.print(
                    "[dim]提示：总结本身可能比原消息更长，建议等待更多对话后再压缩[/dim]"
                )
                return messages
        else:
            old_tokens = self.count_message_tokens(old_messages)
            self.console.print(f"[cyan]即将压缩:[/cyan] {len(old_messages)} 条消息, {old_tokens:,} tokens")

        self.console.print(f"[bold blue]🔄 正在总结 {len(old_messages)} 条历史消息...[/bold blue]")
        with Status("[bold blue]压缩消息中...", spinner="dots"):
            summary = self._summarize_messages(old_messages)

        summary_message = {
            "role": "user",
            "content": f"[历史对话总结]\n{summary}\n[总结结束，以下是最近的对话]",
        }

        compressed_messages = system_messages + [summary_message] + recent_messages

        new_tokens = self.count_message_tokens(compressed_messages)
        saved_tokens = current_tokens - new_tokens

        self.token_stats["compressions"] += 1

        self.console.print("[bold green]✅ 消息压缩完成！[/bold green]")
        self.console.print(
            f"[cyan]压缩前:[/cyan] {len(messages)} 条消息, {current_tokens:,} tokens"
        )
        self.console.print(
            f"[cyan]压缩后:[/cyan] {len(compressed_messages)} 条消息, {new_tokens:,} tokens"
        )
        if current_tokens:
            reduction = saved_tokens / current_tokens * 100
        else:
            reduction = 0
        self.console.print(f"[cyan]节省:[/cyan] {saved_tokens:,} tokens ({reduction:.1f}%)")

        return compressed_messages

    def compress_if_needed(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        current_tokens = self.count_message_tokens(messages)
        if current_tokens <= self.config.max_context_tokens:
            return messages
        self.console.print(
            f"[bold yellow]⚠️  消息历史过长 ({current_tokens:,} tokens > {self.config.max_context_tokens:,} tokens)，正在压缩...[/bold yellow]"
        )
        return self._do_compress_messages(messages, force=True)

    def manual_compress(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        current_tokens = self.count_message_tokens(messages)
        self.console.print("[bold blue]📦 手动压缩消息历史...[/bold blue]")
        self.console.print(f"[cyan]当前状态:[/cyan] {len(messages)} 条消息, {current_tokens:,} tokens")
        return self._do_compress_messages(messages, force=False)

    def serialize_tool_calls(self, tool_calls) -> List[Dict[str, Any]]:
        return [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in tool_calls
        ]
