import argparse
import html
from html.parser import HTMLParser
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests
import yaml


DEFAULT_CONFIG_PATH = "sources.yaml"
DEFAULT_MODEL = "gpt-5-mini"
TELEGRAM_MESSAGE_LIMIT = 4096


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def strip_markup(value: str) -> str:
    parser = TextExtractor()
    parser.feed(html.unescape(value or ""))
    return " ".join(parser.parts).strip()


def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def fetch_entries(sources: list[dict[str, str]], per_source_limit: int = 10) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for source in sources:
        feed = feedparser.parse(source["url"])
        if getattr(feed, "bozo", False):
            print(
                f"Warning: failed to parse feed {source['url']}: {feed.get('bozo_exception')}",
                file=sys.stderr,
            )
        source_name = source.get("name") or feed.feed.get("title") or source["url"]
        for item in feed.entries[:per_source_limit]:
            entries.append(
                {
                    "title": html.unescape(item.get("title", "")).strip(),
                    "summary": strip_markup(item.get("summary", "")),
                    "link": item.get("link", "").strip(),
                    "source": source_name,
                    "published": item.get("published", ""),
                }
            )
    return entries


def filter_entries(
    entries: list[dict[str, str]], keywords: list[str], max_items: int
) -> list[dict[str, str]]:
    seen_links: set[str] = set()
    selected: list[dict[str, str]] = []

    for entry in entries:
        link = entry.get("link", "")
        if link and link in seen_links:
            continue

        haystack = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
        if not any(keyword_matches(keyword, haystack) for keyword in keywords):
            continue

        if link:
            seen_links.add(link)
        selected.append(entry)

        if len(selected) >= max_items:
            break

    return selected


def keyword_matches(keyword: str, haystack: str) -> bool:
    normalized = keyword.lower()
    if normalized.isascii() and len(normalized) <= 3:
        return re.search(rf"\b{re.escape(normalized)}\b", haystack) is not None
    return normalized in haystack


def build_fallback_digest(entries: list[dict[str, str]]) -> str:
    if not entries:
        return "今日 AI 编程新闻\n\n今天没有筛选到足够相关的新闻。"

    lines = ["今日 AI 编程新闻", ""]
    for index, entry in enumerate(entries, start=1):
        lines.extend(
            [
                f"{index}. {entry['title']}",
                f"来源：{entry.get('source', '未知来源')}",
                f"摘要：{entry.get('summary', '').strip() or '原 RSS 未提供摘要。'}",
                f"链接：{entry['link']}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_openai_prompt(entries: list[dict[str, str]]) -> str:
    compact_entries = [
        {
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "source": entry.get("source", ""),
            "link": entry.get("link", ""),
        }
        for entry in entries
    ]
    return (
        "请根据下面的 RSS 条目生成一份中文 Telegram 日报。要求：\n"
        "1. 标题固定为“今日 AI 编程新闻”。\n"
        "2. 最多 8 条，优先选择 AI 编程、代码智能体、IDE、Copilot、Codex、Cursor、Claude Code、开发者工具相关内容。\n"
        "3. 每条包含标题、2 句以内中文摘要、链接。\n"
        "4. 不要编造 RSS 中没有的信息。\n\n"
        f"RSS 条目 JSON：\n{json.dumps(compact_entries, ensure_ascii=False)}"
    )


def extract_response_text(response_json: dict[str, Any]) -> str:
    if isinstance(response_json.get("output_text"), str):
        return response_json["output_text"].strip()

    parts: list[str] = []
    for output in response_json.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def generate_digest(entries: list[dict[str, str]], api_key: str, model: str) -> str:
    if not entries:
        return build_fallback_digest(entries)

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": build_openai_prompt(entries),
            "max_output_tokens": 1400,
        },
        timeout=60,
    )
    response.raise_for_status()
    text = extract_response_text(response.json())
    return text or build_fallback_digest(entries)


def split_telegram_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.extend(line[index : index + limit] for index in range(0, len(line), limit))
            continue

        if len(current) + len(line) > limit:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line

    if current:
        chunks.append(current.rstrip())
    return chunks


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    for chunk in split_telegram_message(text):
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(
                f"Telegram sendMessage failed with {response.status_code}: {response.text}"
            )


def run(config_path: str, dry_run: bool = False) -> str:
    config = load_config(config_path)
    entries = fetch_entries(config["sources"], config.get("per_source_limit", 10))
    selected = filter_entries(
        entries,
        config["keywords"],
        max_items=config.get("max_items", 8),
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    digest = (
        generate_digest(selected, api_key, model)
        if api_key
        else build_fallback_digest(selected)
    )

    footer = datetime.now(timezone.utc).strftime("\n\nGenerated at %Y-%m-%d %H:%M UTC")
    message = f"{digest}{footer}"

    if not dry_run:
        bot_token = require_env("TELEGRAM_BOT_TOKEN")
        chat_id = require_env("TELEGRAM_CHAT_ID")
        send_telegram_message(bot_token, chat_id, message)

    return message


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a daily AI coding news digest to Telegram.")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(run(args.config, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
