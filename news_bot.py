import argparse
from email.utils import parsedate_to_datetime
import html
from html.parser import HTMLParser
import json
import os
import re
import sys
from datetime import datetime, timezone
from time import struct_time
from typing import Any, Optional

import feedparser
import requests
import yaml


DEFAULT_CONFIG_PATH = "sources.yaml"
DEFAULT_MODEL = "gpt-5-mini"
OPENAI_MAX_OUTPUT_TOKENS = 2200
SENT_LINKS_LIMIT = 100
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


def load_sent_links(path: str) -> list[str]:
    if not path or not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, str)]


def save_sent_links(path: str, links: list[str]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(links[-SENT_LINKS_LIMIT:], file, ensure_ascii=False, indent=2)


def filter_sent_entries(
    entries: list[dict[str, str]], sent_links: list[str]
) -> list[dict[str, str]]:
    sent = set(sent_links)
    return [entry for entry in entries if not entry.get("link") or entry.get("link") not in sent]


def remember_sent_entries(
    path: Optional[str], sent_links: list[str], entries: list[dict[str, str]]
) -> None:
    if not path:
        return

    updated = list(sent_links)
    seen = set(updated)
    for entry in entries:
        link = entry.get("link")
        if link and link not in seen:
            updated.append(link)
            seen.add(link)

    save_sent_links(path, updated)


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
                    "published_parsed": item.get("published_parsed") or item.get("updated_parsed"),
                }
            )
    return entries


def filter_entries_by_age(
    entries: list[dict[str, Any]], max_age_hours: int, now: Optional[datetime] = None
) -> list[dict[str, Any]]:
    current_time = now or datetime.now(timezone.utc)
    filtered = []
    for entry in entries:
        published_at = parse_entry_datetime(entry)
        if not published_at:
            filtered.append(entry)
            continue

        age_seconds = (current_time - published_at).total_seconds()
        if 0 <= age_seconds <= max_age_hours * 60 * 60:
            filtered.append(entry)

    return filtered


def parse_entry_datetime(entry: dict[str, Any]) -> Optional[datetime]:
    parsed = entry.get("published_parsed")
    if isinstance(parsed, struct_time):
        return datetime(*parsed[:6], tzinfo=timezone.utc)

    published = entry.get("published")
    if not published:
        return None

    try:
        value = parsedate_to_datetime(published)
    except (TypeError, ValueError):
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def filter_entries(
    entries: list[dict[str, str]], keywords: list[str], max_items: int
) -> list[dict[str, str]]:
    seen_links: set[str] = set()
    selected: list[dict[str, str]] = []

    for entry in entries:
        link = entry.get("link", "")
        if link and link in seen_links:
            continue

        if not is_relevant_entry(entry, keywords):
            continue

        if link:
            seen_links.add(link)
        selected.append(entry)

        if len(selected) >= max_items:
            break

    return selected


def is_relevant_entry(entry: dict[str, str], keywords: list[str]) -> bool:
    title = entry.get("title", "").lower()
    summary = entry.get("summary", "").lower()

    if matched_keywords(keywords, title):
        return True

    return len(matched_keywords(keywords, summary)) >= 2


def matched_keywords(keywords: list[str], haystack: str) -> set[str]:
    return {keyword.lower() for keyword in keywords if keyword_matches(keyword, haystack)}


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
        json=build_openai_request_payload(entries, model),
        timeout=60,
    )
    response.raise_for_status()
    text = extract_response_text(response.json())
    return text or build_fallback_digest(entries)


def build_openai_request_payload(entries: list[dict[str, str]], model: str) -> dict[str, Any]:
    return {
        "model": model,
        "input": build_openai_prompt(entries),
        "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
    }


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
    entries = filter_entries_by_age(entries, config.get("max_age_hours", 36))
    selected = filter_entries(
        entries,
        config["keywords"],
        max_items=config.get("max_items", 8),
    )
    sent_links_path = os.environ.get("SENT_LINKS_PATH")
    sent_links = load_sent_links(sent_links_path) if sent_links_path else []
    selected = filter_sent_entries(selected, sent_links)

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
        remember_sent_entries(sent_links_path, sent_links, selected)

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
