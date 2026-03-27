import os
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    MessagingApi,
    ApiClient,
    Configuration,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

from openai import OpenAI
import sqlite3
import datetime
import traceback

# ===== Flask =====
app = Flask(__name__)


# ===== 讀取環境變數 =====
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# ===== 檢查環境變數 =====
if not CHANNEL_SECRET:
    raise ValueError("CHANNEL_SECRET 沒有設定")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("CHANNEL_ACCESS_TOKEN 沒有設定")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY 沒有設定")


# ===== LINE 設定 =====
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# ===== OpenRouter AI =====
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ===== AI 記憶資料庫 =====
conn = sqlite3.connect("ai_memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS memory(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT,
    created_at TEXT
)
""")

conn.commit()

# ===== 首頁測試 =====
@app.route("/")
def home():
    return "LINE AI Bot is running"


# ===== Webhook =====
@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    print("Webhook Body:", body)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("Webhook Error:", e)
        abort(400)

    return "OK"


# ===== 接收 LINE 訊息 =====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_message = event.message.text
    print("User Message:", user_message)

    try:

        # ===== 呼叫 AI =====
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一個友善的AI助理"},
                {"role": "user", "content": user_message}
            ]
        )

        ai_reply = response.choices[0].message.content

        if not ai_reply:
            ai_reply = "AI 沒有回應"

    except Exception as e:
        print("AI Error:", e)
        ai_reply = "AI 發生錯誤，請稍後再試"

    # ===== 回覆 LINE =====
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=ai_reply)
                    ]
                )
            )

    except Exception as e:
        print("LINE Reply Error:", e)


# ===== Render 啟動 =====
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    print("Server starting on port", port)

    app.run(host="0.0.0.0", port=port)
