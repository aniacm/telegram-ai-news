# Telegram AI Coding News

每天自动抓取 AI 编程相关新闻，生成中文摘要，并推送到 Telegram。

## 你需要准备

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

不要把这些 key 提交到仓库。

## 本地测试

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
python news_bot.py --dry-run
```

如果 dry run 内容看起来正常，再测试 Telegram 发送：

```bash
export OPENAI_API_KEY="你的 OpenAI API key"
export TELEGRAM_BOT_TOKEN="你的 Telegram bot token"
export TELEGRAM_CHAT_ID="你的 Telegram chat id"
python news_bot.py
```

## GitHub Actions 设置

1. 新建一个 GitHub 仓库，把本项目推上去。
2. 打开仓库的 `Settings` -> `Secrets and variables` -> `Actions`。
3. 在 `Repository secrets` 里添加：
   - `OPENAI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. 可选：在 `Variables` 里添加 `OPENAI_MODEL`，默认是 `gpt-5-mini`。
5. 进入 `Actions` 页面，手动运行 `Daily AI Coding News` 测试一次。

默认每天北京时间 09:00 推送。

## 调整新闻源

编辑 `sources.yaml`：

- `sources`：RSS 源列表。
- `keywords`：筛选关键词。
- `max_items`：日报最多新闻条数。
- `per_source_limit`：每个 RSS 源最多读取条数。
- `max_age_hours`：只保留最近多少小时发布的条目，默认 36 小时；没有发布时间的 RSS 条目会保守保留。

## 获取 Telegram Chat ID

1. 给你的 bot 发一条消息。
2. 在浏览器打开：

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

3. 找到返回 JSON 里的 `chat.id`，填入 `TELEGRAM_CHAT_ID`。
