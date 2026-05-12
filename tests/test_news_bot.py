from datetime import datetime, timezone
import os
import tempfile
import unittest
from unittest.mock import Mock, patch


from news_bot import (
    build_fallback_digest,
    build_openai_request_payload,
    filter_entries_by_age,
    filter_sent_entries,
    filter_entries,
    load_sent_links,
    remember_sent_entries,
    send_telegram_message,
    split_telegram_message,
    strip_markup,
)


class NewsBotTest(unittest.TestCase):
    def test_filter_entries_keeps_ai_coding_matches_and_limits_results(self):
        entries = [
            {
                "title": "Cursor improves background agents",
                "summary": "New coding agent workflow for large codebases.",
                "link": "https://example.com/cursor",
                "source": "Example",
            },
            {
                "title": "General AI chip funding news",
                "summary": "No programming workflow update here.",
                "link": "https://example.com/chip",
                "source": "Example",
            },
            {
                "title": "GitHub Copilot adds review support",
                "summary": "Developers can review pull requests faster.",
                "link": "https://example.com/copilot",
                "source": "Example",
            },
        ]

        result = filter_entries(entries, ["cursor", "copilot", "codex"], max_items=1)

        self.assertEqual(result, [entries[0]])

    def test_filter_entries_deduplicates_by_link(self):
        entries = [
            {
                "title": "OpenAI Codex ships update",
                "summary": "Coding assistant news.",
                "link": "https://example.com/codex",
                "source": "A",
            },
            {
                "title": "OpenAI Codex ships update again",
                "summary": "Same link from another feed.",
                "link": "https://example.com/codex",
                "source": "B",
            },
        ]

        result = filter_entries(entries, ["codex"], max_items=5)

        self.assertEqual(result, [entries[0]])

    def test_filter_entries_uses_word_boundaries_for_short_english_keywords(self):
        entries = [
            {
                "title": "OpenAI Campus Network welcomes clubs worldwide",
                "summary": "Build an AI-powered campus community.",
                "link": "https://example.com/campus",
                "source": "OpenAI Blog",
            },
            {
                "title": "New IDE assistant improves code review",
                "summary": "Developer workflow update.",
                "link": "https://example.com/ide",
                "source": "Example",
            },
        ]

        result = filter_entries(entries, ["IDE"], max_items=5)

        self.assertEqual(result, [entries[1]])

    def test_filter_entries_ignores_single_summary_keyword_from_boilerplate(self):
        entries = [
            {
                "title": "Google DeepMind's powerful AI co-mathematician",
                "summary": "Today's AI research update. Automate any manual task with Codex.",
                "link": "https://example.com/deepmind",
                "source": "The Rundown AI",
            },
            {
                "title": "Agents for Everything Else: Codex for Knowledge Work",
                "summary": "Coding agents are expanding from codebases to broader workflows.",
                "link": "https://example.com/codex-agents",
                "source": "Latent Space",
            },
        ]

        result = filter_entries(entries, ["codex", "coding agent", "codebase"], max_items=5)

        self.assertEqual(result, [entries[1]])

    def test_filter_entries_keeps_summary_with_multiple_relevant_keywords(self):
        entries = [
            {
                "title": "A new workflow for large teams",
                "summary": "This coding agent reviews pull requests across large codebases.",
                "link": "https://example.com/workflow",
                "source": "Example",
            },
        ]

        result = filter_entries(entries, ["coding agent", "pull request", "codebase"], max_items=5)

        self.assertEqual(result, entries)

    def test_filter_sent_entries_removes_links_already_sent(self):
        entries = [
            {"title": "Old Codex item", "link": "https://example.com/old"},
            {"title": "New Claude Code item", "link": "https://example.com/new"},
        ]

        result = filter_sent_entries(entries, ["https://example.com/old"])

        self.assertEqual(result, [entries[1]])

    def test_filter_entries_by_age_keeps_recent_and_unknown_dates(self):
        entries = [
            {
                "title": "Old Codex item",
                "published": "Sun, 10 May 2026 00:00:00 GMT",
                "link": "https://example.com/old",
            },
            {
                "title": "Recent Claude Code item",
                "published": "Tue, 12 May 2026 00:00:00 GMT",
                "link": "https://example.com/recent",
            },
            {
                "title": "Unknown date item",
                "published": "",
                "link": "https://example.com/unknown",
            },
        ]

        result = filter_entries_by_age(
            entries,
            max_age_hours=36,
            now=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result, [entries[1], entries[2]])

    def test_remember_sent_entries_persists_links(self):
        entries = [
            {"title": "Codex", "link": "https://example.com/codex"},
            {"title": "Claude Code", "link": "https://example.com/claude-code"},
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "sent_links.json")
            remember_sent_entries(path, ["https://example.com/existing"], entries)

            links = load_sent_links(path)

        self.assertEqual(
            links,
            [
                "https://example.com/existing",
                "https://example.com/codex",
                "https://example.com/claude-code",
            ],
        )

    def test_build_fallback_digest_formats_chinese_daily_message(self):
        entries = [
            {
                "title": "GitHub Copilot adds review support",
                "summary": "Developers can review pull requests faster.",
                "link": "https://example.com/copilot",
                "source": "GitHub Blog",
            }
        ]

        message = build_fallback_digest(entries)

        self.assertIn("今日 AI 编程新闻", message)
        self.assertIn("1. GitHub Copilot adds review support", message)
        self.assertIn("来源：GitHub Blog", message)
        self.assertIn("https://example.com/copilot", message)

    def test_strip_markup_removes_html_tags_and_unescapes_entities(self):
        text = strip_markup("<p>Agentic workflows &amp; coding tools.</p>")

        self.assertEqual(text, "Agentic workflows & coding tools.")

    def test_build_openai_request_payload_allows_long_enough_digest(self):
        payload = build_openai_request_payload(
            [{"title": "Claude Code", "summary": "Prompt caching", "source": "Claude", "link": "x"}],
            "gpt-5-mini",
        )

        self.assertGreaterEqual(payload["max_output_tokens"], 2200)

    def test_split_telegram_message_keeps_chunks_under_limit(self):
        message = "标题\n\n" + "\n".join(f"{index}. {'x' * 900}" for index in range(1, 7))

        chunks = split_telegram_message(message, limit=1000)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 1000 for chunk in chunks))
        self.assertEqual("".join(chunks).replace("\n\n", "\n").count("1."), 1)

    @patch("news_bot.requests.post")
    def test_send_telegram_message_includes_response_body_on_failure(self, mock_post):
        response = Mock()
        response.ok = False
        response.status_code = 400
        response.text = '{"ok":false,"description":"Bad Request: chat not found"}'
        mock_post.return_value = response

        with self.assertRaisesRegex(RuntimeError, "chat not found"):
            send_telegram_message("token", "bad-chat-id", "hello")


if __name__ == "__main__":
    unittest.main()
