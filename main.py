import os
import time
import threading
import logging

import requests
from flask import Flask, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get(
    "WEBAPP_URL",
    "https://55prosek-lgtm.github.io/electro-predpisaniya/"
)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)


@app.get("/")
def health():
    return jsonify({
        "status": "running",
        "application": "ElectroPredpisaniyaBot"
    })


def telegram_request(method, data=None, timeout=35):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    response = requests.post(
        f"{TELEGRAM_API}/{method}",
        json=data or {},
        timeout=timeout
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API error"))

    return result.get("result")


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    telegram_request("sendMessage", data, timeout=20)


def handle_update(update):
    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if text.startswith("/start"):
        keyboard = {
            "keyboard": [[
                {
                    "text": "🚀 Открыть ЭлектроПодряд",
                    "web_app": {"url": WEBAPP_URL}
                }
            ]],
            "resize_keyboard": True
        }

        send_message(
            chat_id,
            "⚡ ЭлектроПодряд\n\n"
            "Приложение учёта предписаний готово к подключению.\n"
            "Нажми кнопку ниже, чтобы открыть интерфейс.",
            keyboard
        )

    elif text == "/help":
        send_message(
            chat_id,
            "Доступные команды:\n"
            "/start — открыть приложение\n"
            "/help — помощь"
        )


def polling_loop():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing. Configure it in Render Environment.")
        return

    offset = None

    while True:
        try:
            params = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset

            response = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params=params,
                timeout=35
            )
            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                logger.error("Telegram polling error: %s", result)
                time.sleep(5)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1

                try:
                    handle_update(update)
                except Exception:
                    logger.exception("Failed to handle update")

        except Exception:
            logger.exception("Polling failed")
            time.sleep(5)


if BOT_TOKEN:
    threading.Thread(target=polling_loop, daemon=True).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
