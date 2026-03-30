import os
from flask import Flask, request, abort

from memory.memory_manager import MemoryManager

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

import traceback

# AI Client
from ai.ai_client import AIClient


# ===== 初始化 AI =====
ai = AIClient()


# ===== Flask =====
app = Flask(__name__)

memory_manager = MemoryManager()


# ===== 讀取環境變數 =====
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not CHANNEL_SECRET:
    raise ValueError("CHANNEL_SECRET 沒有設定")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("CHANNEL_ACCESS_TOKEN 沒有設定")


# ===== LINE 設定 =====
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# ===== 健康檢查 =====
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

    # ===== 手動記住 =====
    if user_message.startswith("記住"):

        memory_text = user_message.replace("記住", "").strip()

        if memory_text:
            memory_manager.save_memory(user_id, memory_text)

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

        memories = memory_manager.get_memory(user_id)

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

        memories = memory_manager.get_memory(user_id)
        memory_text = "\n".join(memories)

        messages = [
            {
                "role": "system",
                "content": f"""
你是一個友善、可靠、會記住使用者資訊的 AI 助理。

以下是使用者的重要記憶：
{memory_text}

如果使用者說出「長期資訊」，例如：
- 喜好
- 興趣
- 工作
- 身分
- 生活習慣
- 目標

請在回答最後加上一行：

MEMORY: 要記住的資訊

例如：

使用者說：
我每天喝咖啡

回答：
原來你很喜歡咖啡！

MEMORY: 使用者每天喝咖啡

如果沒有需要記憶的資訊，就不要輸出 MEMORY。
"""
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
        ai_reply = ai.chat(messages)

        # ===== AI 自動記憶 =====
        if "MEMORY:" in ai_reply:

            parts = ai_reply.split("MEMORY:")

            clean_reply = parts[0].strip()

            if len(parts) > 1:

                memory_text = parts[1].strip()

                if memory_text:
                    memory_manager.save_memory(user_id, memory_text)
                    print("AI Memory Saved:", memory_text)

            ai_reply = clean_reply

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
