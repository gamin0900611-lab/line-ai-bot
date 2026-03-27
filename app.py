from flask import Flask, request, abort
import os
import requests
import sqlite3
import datetime
import threading
import time
import traceback
import pytz
import re
import schedule
import urllib.parse

app = Flask(__name__)

from openai import OpenAI

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    MessagingApi,
    Configuration,
    ApiClient,
    ReplyMessageRequest,
    TextMessage
)

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
handler = WebhookHandler(LINE_CHANNEL_SECRET)

configuration = Configuration(
    access_token=LINE_CHANNEL_ACCESS_TOKEN
)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_text = event.message.text

    try:

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "user", "content": user_text}
            ]
        )

        reply_text = response.choices[0].message.content

    except Exception as e:

        print("AI error:", e)
        reply_text = "AI 發生錯誤"

    with ApiClient(configuration) as api_client:

        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=reply_text)
                ]
            )
        )

# OpenRouter AI
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# Webhook
@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(e)
        abort(400)

    return "OK"


# LINE 收到訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_text = event.message.text

    try:

        completion = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一個聰明的AI生活助理"},
                {"role": "user", "content": user_text}
            ]
        )

        ai_reply = completion.choices[0].message.content

    except Exception as e:

        ai_reply = "AI 發生錯誤"

        print(e)

    with ApiClient(configuration) as api_client:

        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=ai_reply)]
            )
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
