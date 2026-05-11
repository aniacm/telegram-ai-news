import unittest


from news_bot import build_fallback_digest, filter_entries, strip_markup


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


if __name__ == "__main__":
    unittest.main()
