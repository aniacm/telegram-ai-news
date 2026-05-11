# Telegram AI News Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub Actions based Telegram bot that sends a daily Chinese digest of AI programming news.

**Architecture:** A small Python CLI reads RSS sources, filters entries by AI coding keywords, asks OpenAI to produce a concise Chinese digest, then sends it to Telegram. Tests cover pure filtering, formatting, and configuration behavior without making network calls.

**Tech Stack:** Python 3.11, feedparser, requests, PyYAML, pytest, GitHub Actions cron.

---

### File Structure

- `news_bot.py`: CLI, RSS loading, entry filtering, OpenAI digest generation, Telegram sending.
- `sources.yaml`: Curated RSS sources and keyword configuration.
- `requirements.txt`: Runtime and test dependencies.
- `.github/workflows/daily.yml`: Scheduled and manual GitHub Actions workflow.
- `.env.example`: Local environment variable template.
- `README.md`: Setup instructions for Telegram, OpenAI, local test run, and GitHub Secrets.
- `tests/test_news_bot.py`: Unit tests for filtering and message fallback behavior.

### Task 1: Filtering And Digest Fallback

- [ ] Write tests for keyword filtering, deduplication, max item limiting, and fallback digest formatting.
- [ ] Run `pytest` and verify tests fail because `news_bot.py` does not exist.
- [ ] Implement minimal pure functions in `news_bot.py`.
- [ ] Run `pytest` and verify tests pass.

### Task 2: Network Integrations

- [ ] Add RSS fetching with `feedparser`.
- [ ] Add OpenAI Responses API HTTP call using `OPENAI_API_KEY`.
- [ ] Add Telegram `sendMessage` HTTP call using `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- [ ] Keep network functions small so they can be tested or mocked later.

### Task 3: Automation And Docs

- [ ] Add `sources.yaml` with initial AI programming sources and keywords.
- [ ] Add GitHub Actions workflow running daily and via manual dispatch.
- [ ] Add `.env.example` and README instructions.
- [ ] Run syntax checks and unit tests before reporting completion.
