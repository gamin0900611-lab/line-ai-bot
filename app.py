from flask import Flask, request
import requests
from openai import OpenAI
import sqlite3
import datetime
import schedule
import time
import threading
import urllib.parse
import re
import os

app = Flask(__name__)

# 🔥 雙模式 KEY（本地 + 雲端）
LINE_TOKEN = os.environ.get("LINE_TOKEN") or "1O2oOqz3rG5OkdVT2OSSQN3FyJuiFeX53iCp2UB3PbgEO93ZMlNDxRsgmcmraqmbxvj5K/x1w/HTP5a+3bVl0VIJmrKJlp5kIUKl7yylpyXzmiXpnBwumrSwYMOAs75nTY3yny5YkGD5rcmfjZRNaQdB04t89/1O/w1cDnyilFU="
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or "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"

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# 💰 防爆
user_usage = {}
DAILY_LIMIT = 50

# 🔔 防重複提醒
notified = set()

# 📦 DB
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

# 📅 行程
cursor.execute("""
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    time TEXT,
    text TEXT,
    location TEXT,
    repeat_type TEXT
)
""")

# 🧠 記憶
cursor.execute("""
CREATE TABLE IF NOT EXISTS memory (
    user_id TEXT,
    role TEXT,
    content TEXT
)
""")

# 🎯 目標
cursor.execute("""
CREATE TABLE IF NOT EXISTS goals (
    user_id TEXT,
    goal_name TEXT,
    target TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS goal_logs (
    user_id TEXT,
    goal_name TEXT,
    value TEXT,
    time TEXT
)
""")

conn.commit()

# 📩 推播
def push_message(uid, text):
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        json={"to": uid, "messages": [{"type": "text", "text": text}]}
    )

# 🤖 AI（最強穩定版）
def call_ai(messages, task="chat"):
    models = [
        # 🥇 免費優先（最穩）
        "mistralai/mistral-7b-instruct",

        # 🥈 備用免費
        "openai/gpt-3.5-turbo",

        # 🥉 有錢才用
        "openai/gpt-4o-mini"
    ]

    for model in models:
        try:
            print(f"嘗試模型: {model}")

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=300
            )

            # ✅ 正常回傳內容
            content = response.choices[0].message.content
            print(f"成功模型: {model}")
            return content

        except Exception as e:
            print(f"模型失敗: {model}", e)

    # ❗ 全部失敗
    return "AI目前無法使用（模型全部失敗）"
# 🌐 查詢
def web_search(query):
    url = "https://api.duckduckgo.com/?q=" + urllib.parse.quote(query) + "&format=json"
    res = requests.get(url).json()

    if res.get("AbstractText"):
        return res["AbstractText"]

    for t in res.get("RelatedTopics", []):
        if "Text" in t:
            return t["Text"]

    return "查不到"

# 📰 新聞
def get_news():
    raw = web_search("台灣新聞")
    res = call_ai([
        {"role": "system", "content": "整理3條重要新聞"},
        {"role": "user", "content": raw}
    ], "analysis")
    return res.choices[0].message.content

# 🧠 自然語言時間
def parse_event(msg):
    now = datetime.datetime.now()
    hour, minute = None, 0
    month, day = now.month, now.day
    repeat_type = "none"

    if "明天" in msg:
        d = now + datetime.timedelta(days=1)
        month, day = d.month, d.day

    if "每天" in msg:
        repeat_type = "daily"

    if "每週" in msg:
        repeat_type = "weekly"

    m = re.search(r"(\d{1,2})/(\d{1,2})", msg)
    if m:
        month, day = int(m.group(1)), int(m.group(2))

    m1 = re.search(r"(\d{1,2}):(\d{1,2})", msg)
    m2 = re.search(r"(\d{1,2})點(\d{1,2})?", msg)

    if m1:
        hour, minute = int(m1.group(1)), int(m1.group(2))
    elif m2:
        hour = int(m2.group(1))
        if m2.group(2):
            minute = int(m2.group(2))
    else:
        return None

    location = msg.split("在")[-1] if "在" in msg else ""
    dt = datetime.datetime(now.year, month, day, hour, minute)

    if dt < now:
        dt += datetime.timedelta(days=1)

    return dt, location, repeat_type

# ⏰ 提醒
def check_schedule():
    now = datetime.datetime.now()
    rows = cursor.execute("SELECT * FROM schedule").fetchall()

    for r in rows:
        sid, uid, t, text, loc, rep = r
        event_time = datetime.datetime.fromisoformat(t)

        if rep == "daily":
            while event_time < now:
                event_time += datetime.timedelta(days=1)

        if rep == "weekly":
            while event_time < now:
                event_time += datetime.timedelta(days=7)

        diff = (event_time - now).total_seconds()

        if 540 <= diff <= 600 and f"{sid}_10" not in notified:
            notified.add(f"{sid}_10")
            push_message(uid, f"⏰ 10分鐘後：{text}")

        if -30 <= diff <= 30 and f"{sid}_now" not in notified:
            notified.add(f"{sid}_now")
            push_message(uid, f"🚨 現在：{text}")

# 🌅 早安（完整版🔥）
def morning():
    users = cursor.execute("SELECT DISTINCT user_id FROM schedule").fetchall()
    news = get_news()
    today = datetime.date.today()

    for (uid,) in users:
        rows = cursor.execute("SELECT time, text FROM schedule WHERE user_id=?", (uid,)).fetchall()

        events = []
        for t, text in rows:
            dt = datetime.datetime.fromisoformat(t)
            if dt.date() == today:
                events.append(f"{dt.strftime('%H:%M')} {text}")

        msg = "🌅 早安！\n\n📊 今日行程：\n"
        msg += "\n".join(events) if events else "今天沒行程 👍"
        msg += "\n\n📰 新聞：\n" + news

        push_message(uid, msg)

# 🔔 排程執行
def run_schedule():
    schedule.every(1).minutes.do(check_schedule)
    schedule.every().day.at("05:00").do(morning)

    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_schedule).start()

# 🎯 Webhook
@app.route("/webhook", methods=['POST'])
def webhook():
    try:
        data = request.json
        event = data['events'][0]

        user_id = event['source']['userId']
        user_msg = event['message']['text']
        reply_token = event['replyToken']

        print("使用者:", user_msg)

        # 🧠 存記憶
        cursor.execute("INSERT INTO memory VALUES (?, ?, ?)", (user_id, "user", user_msg))
        conn.commit()

        # 💰 使用次數
        user_usage[user_id] = user_usage.get(user_id, 0) + 1

        if user_usage[user_id] > DAILY_LIMIT:
            ai_reply = "今日已達上限"

        # 🎯 目標設定
        elif user_msg.startswith("/目標"):
            _, g, t = user_msg.split()
            cursor.execute("INSERT INTO goals VALUES (?, ?, ?)", (user_id, g, t))
            conn.commit()
            ai_reply = "已設定目標"

        # 📝 打卡
        elif user_msg.startswith("/打卡"):
            _, g, v = user_msg.split()
            cursor.execute("INSERT INTO goal_logs VALUES (?, ?, ?, ?)",
                           (user_id, g, v, str(datetime.datetime.now())))
            conn.commit()
            ai_reply = "已記錄"

        # 📊 進度分析
        elif user_msg == "/進度":
            rows = cursor.execute("SELECT * FROM goal_logs WHERE user_id=?", (user_id,)).fetchall()
            ai_reply = call_ai([{"role": "user", "content": str(rows)}])

        # 🌐 查詢
        elif user_msg.startswith("/查"):
            q = user_msg.replace("/查", "")
            data = web_search(q)
            ai_reply = call_ai([{"role": "user", "content": data}])

        # 📈 行程分析
        elif user_msg == "/分析":
            rows = cursor.execute("SELECT text FROM schedule WHERE user_id=?", (user_id,)).fetchall()
            ai_reply = call_ai([{"role": "user", "content": str(rows)}])

        # 📅 新增行程（自然語言）
        elif any(x in user_msg for x in ["點", ":", "/", "月"]):
            parsed = parse_event(user_msg)
            if parsed:
                dt, loc, rep = parsed
                cursor.execute("INSERT INTO schedule VALUES (NULL,?,?,?,?,?)",
                               (user_id, str(dt), user_msg, loc, rep))
                conn.commit()
                ai_reply = "已新增行程"
            else:
                ai_reply = "時間解析失敗"

        # 🤖 一般聊天（最重要🔥）
        else:
            ai_reply = call_ai([{"role": "user", "content": user_msg}])

        print("AI回覆:", ai_reply)

        # 🧠 存 AI 回覆
        cursor.execute("INSERT INTO memory VALUES (?, ?, ?)", (user_id, "assistant", ai_reply))
        conn.commit()

        # 📩 回 LINE（只能一次🔥）
        requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={
                "Authorization": f"Bearer {LINE_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": ai_reply}]
            }
        )

    except Exception as e:
        print("Webhook錯誤:", e)

    return "OK"
# 🚀 啟動（雲端OK）
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
