import os
import traceback
import datetime
import threading

from flask import Flask, request, abort

from memory.memory_manager import MemoryManager
from core.personality import get_system_prompt
from core.cost_guard import CostGuard
from core.calendar_manager import CalendarManager
from core.utils.web_search import web_search
from core.utils.reminder_service import ReminderService
from ai.ai_client import AIClient

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
# ===== 初始化 =====

app = Flask(__name__)

ai = AIClient()
memory_manager = MemoryManager()
cost_guard = CostGuard()
calendar_manager = CalendarManager()
# ===== Reminder service =====

reminder_service = ReminderService(
    calendar_manager,
    configuration
)

threading.Thread(
    target=reminder_service.start,
    daemon=True
).start()

# ===== LINE 環境變數 =====

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not CHANNEL_SECRET:
    raise ValueError("CHANNEL_SECRET 沒有設定")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("CHANNEL_ACCESS_TOKEN 沒有設定")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ===== 健康檢查 =====

@app.route("/")
def home():
    return "LINE AI Bot is running"


# ===== Webhook =====

@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers.get("X-Line-Signature")
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

    # ===== 所有行程 =====

    if user_message == "所有行程":

        events = calendar_manager.get_all_events(user_id)

        if not events:
            reply_line(event, "目前沒有行程")
            return

        text = "📅 所有行程\n\n"

        for i, (title, time) in enumerate(events, 1):
            text += f"{i}. {time} {title}\n"

        text += "\n刪除行程請輸入：刪除 1"

        reply_line(event, text)
        return


    # ===== 刪除行程 =====

    if user_message.startswith("刪除"):

        try:

            event_id = int(user_message.replace("刪除", "").strip())

            calendar_manager.delete_event(event_id)

            reply_line(event, "行程已刪除")

        except:

            reply_line(event, "格式：刪除 1")

        return


    # ===== 手動記住 =====

    if user_message.startswith("記住"):

        memory_text = user_message.replace("記住", "").strip()

        if memory_text:
            memory_manager.save_memory(user_id, memory_text)

        reply_line(event, f"我記住了：{memory_text}")
        return

    # ===== 今天行程 =====

    if user_message == "今天行程":

        today = datetime.date.today()

        events = calendar_manager.get_events_by_date(
            user_id,
            str(today)
        )

        if not events:
            reply_line(event, "今天沒有行程")
            return

        text = "📅 今天行程\n\n"

        for eid, title, time in events:

            hour = time.split(" ")[1]

            text += f"{hour} {title}\n"

        reply_line(event, text)
        return


    # ===== 明天行程 =====

    if user_message == "明天行程":

        tomorrow = datetime.date.today() + datetime.timedelta(days=1)

        events = calendar_manager.get_events_by_date(
            user_id,
            str(tomorrow)
        )

        if not events:
            reply_line(event, "明天沒有行程")
            return

        text = "📅 明天行程\n\n"

        for eid, title, time in events:

            hour = time.split(" ")[1]

            text += f"{hour} {title}\n"

        reply_line(event, text)
        return

    # ===== AI 生活分析 =====

    if "分析" in user_message:

        memories = memory_manager.get_memory(user_id)
        memory_text = "\n".join(memories)

        analysis_prompt = f"""
以下是使用者的所有長期記憶：

{memory_text}

請幫使用者做生活分析：

1. 使用者目前的習慣
2. 使用者的目標
3. 可能的問題
4. 可以優化的地方
5. 三個具體建議

請用簡單清楚的方式回答。
"""

        messages = [
            {"role": "system", "content": "你是一位生活教練 AI"},
            {"role": "user", "content": analysis_prompt}
        ]

        ai_reply = ai.chat(messages)

        reply_line(event, ai_reply)

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

        reply_line(event, reply_text)
        return

    # ===== 呼叫 AI =====

    try:

        memories = memory_manager.get_memory(user_id)
        memory_text = "\n".join(memories)

        system_prompt = get_system_prompt(memory_text)

        # ===== Web Search =====

        search_keywords = [
            "新聞", "股價", "多少", "什麼是",
            "誰是", "查詢", "查一下",
            "現在", "today", "news"
        ]

        need_search = any(k in user_message for k in search_keywords)

        if need_search:

            print("Web search triggered")

            search_result = web_search(user_message)

            user_message = f"""
使用者問題：
{user_message}

以下是網路搜尋結果：
{search_result}

請根據搜尋結果回答。
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # ===== 成本防爆 =====

        if not cost_guard.allow_request(1000):
            reply_line(event, "今日 AI 使用額度已達上限")
            return

        ai_reply = ai.chat(messages)

        print("AI reply:", ai_reply)

        cost_guard.add_usage(1000)

        # ===== AI 行程解析 =====

        if "EVENT:" in ai_reply:

            try:

                parts = ai_reply.split("EVENT:")
                clean_reply = parts[0].strip()

                event_text = parts[1].strip()

                if "|" in event_text:

                    title, time_text = event_text.split("|", 1)

                    event_time = calendar_manager.parse_time(time_text)

                    calendar_manager.add_event(
                        user_id,
                        title.strip(),
                        event_time
                    )

                ai_reply = clean_reply

            except Exception as e:

                print("Event parse error:", e)

        # ===== AI 記憶解析 =====

        if "MEMORY:" in ai_reply:

            try:

                parts = ai_reply.split("MEMORY:")
                clean_reply = parts[0].strip()

                memory_text = parts[1].strip()

                if memory_text:
                    memory_manager.save_memory(user_id, memory_text)

                ai_reply = clean_reply

            except Exception as e:

                print("Memory parse error:", e)

    except Exception as e:

        print("AI Error:", e)
        traceback.print_exc()

        ai_reply = "AI 發生錯誤"

    # ===== 回覆 LINE =====

    reply_line(event, ai_reply)


# ===== LINE 回覆函數 =====

def reply_line(event, text):

    try:

        with ApiClient(configuration) as api_client:

            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
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
