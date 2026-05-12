# Telegram AI Coding News

Automatically fetch AI coding news every day, generate a Chinese digest, and send it to Telegram.

## Requirements

You need these secrets:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Do not commit any of these values to the repository.

## Local Testing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
python news_bot.py --dry-run
```

If the dry run output looks good, test Telegram delivery:

```bash
export OPENAI_API_KEY="your OpenAI API key"
export TELEGRAM_BOT_TOKEN="your Telegram bot token"
export TELEGRAM_CHAT_ID="your Telegram chat id"
python news_bot.py
```

## GitHub Actions Setup

1. Create a GitHub repository and push this project to it.
2. Open `Settings` -> `Secrets and variables` -> `Actions`.
3. Add these `Repository secrets`:
   - `OPENAI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. Optional: add `OPENAI_MODEL` under `Variables`. The default model is `gpt-5-mini`.
5. Open the `Actions` tab and manually run `Daily AI Coding News` once to test it.

By default, the workflow sends the digest every day at 09:00 Beijing time.

## News Sources

Edit `sources.yaml` to adjust:

- `sources`: RSS feed list.
- `keywords`: filtering keywords.
- `max_items`: maximum number of items in each digest.
- `per_source_limit`: maximum number of entries to read from each feed.
- `max_age_hours`: only keep entries published within this many hours. The default is 36 hours; entries without a publication time are kept conservatively.

The current default sources come from the Feedly `Daily AI` OPML export:

- The Rundown AI
- Latent Space
- Claude Blog
- OpenAI News
- Simon Willison

## Get Telegram Chat ID

1. Send a message to your Telegram bot.
2. Open this URL in a browser:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

3. Find `chat.id` in the returned JSON and use it as `TELEGRAM_CHAT_ID`.
