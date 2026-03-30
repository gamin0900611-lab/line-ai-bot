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

# ===== AI 記憶資料庫 =====
def init_db():

    conn = sqlite3.connect("memory.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        memory TEXT
    )
    """)

    conn.commit()
    conn.close()


# ===== 讀取記憶 =====
def get_memory(user_id):

    conn = sqlite3.connect("memory.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT memory FROM memories WHERE user_id = ?",
        (user_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    memories = [row[0] for row in rows]

    return memories


# ===== 儲存記憶 =====
def save_memory(user_id, memory):

    conn = sqlite3.connect("memory.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO memories (user_id, memory) VALUES (?, ?)",
        (user_id, memory)
    )

    conn.commit()
    conn.close()

# ===== Flask =====
app = Flask(__name__)
init_db()

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
    user_id = event.source.user_id

    print("User Message:", user_message)

    # ===== 記住功能 =====
    if user_message.startswith("記住"):

        memory_text = user_message.replace("記住", "").strip()

        if memory_text:
            save_memory(user_id, memory_text)

        reply_text = f"我記住了：{memory_text}"

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

        return


    # ===== 查看記憶 =====
    if user_message == "我的記憶":

        memories = get_memory(user_id)

        if not memories:
            reply_text = "我目前沒有記憶"

        else:
            memory_list = []

            for m in memories:
                memory_list.append("• " + m)

            reply_text = "你的記憶：\n" + "\n".join(memory_list)

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

        return

    # ===== 呼叫 AI =====
    try:

        memories = get_memory(user_id)
        memory_text = "\n".join(memories)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
你是一個友善的AI助理。

這是使用者的重要記憶：
{memory_text}

如果使用者說出「長期資訊」，例如：
喜好、目標、身分、習慣、工作、生活資訊

請在回答最後加上一行：

MEMORY: 要記住的內容

例如：

使用者說：
我喜歡咖啡

回答：
原來你喜歡咖啡！

MEMORY: 使用者喜歡咖啡

如果沒有需要記憶的資訊，就不要輸出 MEMORY。
"""
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        ai_reply = response.choices[0].message.content


    # ===== AI 自動記憶 =====
    if "MEMORY:" in ai_reply:

        parts = ai_reply.split("MEMORY:")

        ai_reply = parts[0].strip()

        if len(parts) > 1:

            memory_text = parts[1].strip()

            if memory_text:
                save_memory(user_id, memory_text)
                print("AI Memory Saved:", memory_text)


    if not ai_reply:
        ai_reply = "AI 沒有回應"


except Exception as e:

    print("AI Error:", e)
    traceback.print_exc()

    ai_reply = "AI 發生錯誤，請稍後再試"


# ===== 回覆 LINE =====
try:

     with ApiClient(configuration) as api_client:

            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=ai_reply)]
                )
            )

    except Exception as e:

        print("LINE Reply Error:", e)
        traceback.print_exc()

# ===== Render 啟動 =====
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    print("Server starting on port", port)

    app.run(host="0.0.0.0", port=port)
