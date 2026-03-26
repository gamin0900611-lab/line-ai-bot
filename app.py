# ==========================================
# LINE AI ASSISTANT SYSTEM
# Core System
# ==========================================

from flask import Flask, request
import requests
import sqlite3
import datetime
import os
import threading
import time
import traceback
import pytz
import re
import schedule
import urllib.parse

from openai import OpenAI


# ==========================================
# 基本設定
# ==========================================

app = Flask(__name__)

# Render port
PORT = int(os.environ.get("PORT", 10000))

# 時區
tz = pytz.timezone("Asia/Taipei")

# API KEY
LINE_TOKEN = os.environ.get("1O2oOqz3rG5OkdVT2OSSQN3FyJuiFeX53iCp2UB3PbgEO93ZMlNDxRsgmcmraqmbxvj5K/x1w/HTP5a+3bVl0VIJmrKJlp5kIUKl7yylpyXzmiXpnBwumrSwYMOAs75nTY3yny5YkGD5rcmfjZRNaQdB04t89/1O/w1cDnyilFU=")
OPENROUTER_API_KEY = os.environ.get("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")

# OpenRouter
import os
from openai import OpenAI

client = OpenAI(
    api_key="sk-or-v1-390854de32200b8e0960bb1b5887fd8818ecea34002ba5cf0f24a44359fd100"
    base_url="https://openrouter.ai/api/v1"
))
# AI模型
AI_MODEL = "openai/gpt-4o-mini"

# 每日使用上限
DAILY_LIMIT = 500

# 使用紀錄
user_usage = {}


# ==========================================
# 資料庫
# ==========================================

conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

# 對話記憶
cursor.execute("""
CREATE TABLE IF NOT EXISTS memory (
    user_id TEXT,
    role TEXT,
    content TEXT,
    time TEXT
)
""")

# 長期記憶
cursor.execute("""
CREATE TABLE IF NOT EXISTS profile (
    user_id TEXT PRIMARY KEY,
    summary TEXT
)
""")

# 行程
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

# 目標
cursor.execute("""
CREATE TABLE IF NOT EXISTS goals (
    user_id TEXT,
    goal TEXT,
    target TEXT
)
""")

# 打卡
cursor.execute("""
CREATE TABLE IF NOT EXISTS goal_logs (
    user_id TEXT,
    goal TEXT,
    value TEXT,
    time TEXT
)
""")

# 花費
cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    user_id TEXT,
    amount REAL,
    category TEXT,
    note TEXT,
    time TEXT
)
""")

conn.commit()


# ==========================================
# AI人格
# ==========================================

SYSTEM_PROMPT = """
你是一個個人AI助理。

功能：
1. 管理行程
2. 記住使用者習慣
3. 財務分析
4. 目標追蹤
5. 每日與每週報告

規則：
- 使用繁體中文
- 回覆清晰簡短
- 若有行程或金錢資料要分析
"""



# ==========================================
# AI呼叫
# ==========================================

def call_ai(messages):

    now = datetime.datetime.now(tz)

    system_time = f"""
現在時間：{now}
時區：Asia/Taipei
"""

    full_messages = [
        {"role": "system", "content": SYSTEM_PROMPT + system_time}
    ] + messages

    try:

        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=full_messages,
            max_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:

        print("AI錯誤", e)

        return "AI暫時無法回應"



# ==========================================
# LINE 回覆
# ==========================================

def reply_message(token, text):

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "replyToken": token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    try:

        requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers=headers,
            json=data
        )

    except Exception as e:

        print("LINE錯誤", e)



# ==========================================
# LINE 推播
# ==========================================

def push_message(uid, text):

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "to": uid,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    try:

        requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers=headers,
            json=data
        )

    except Exception as e:

        print("push錯誤", e)



# ==========================================
# Web搜尋
# ==========================================

def web_search(query):

    url = "https://api.duckduckgo.com/?q=" + urllib.parse.quote(query) + "&format=json"

    try:

        res = requests.get(url).json()

        if res.get("AbstractText"):
            return res["AbstractText"]

        for t in res.get("RelatedTopics", []):

            if "Text" in t:
                return t["Text"]

    except:
        pass

    return "查不到資料"



# ==========================================
# 取得今天行程
# ==========================================

def get_today_events(user_id):

    today = datetime.date.today()

    rows = cursor.execute(
        "SELECT time,text FROM schedule WHERE user_id=?",
        (user_id,)
    ).fetchall()

    events = []

    for t, text in rows:

        dt = datetime.datetime.fromisoformat(t)

        if dt.date() == today:

            events.append(
                f"{dt.strftime('%H:%M')} {text}"
            )

    return events

# ==========================================
# 中文時間解析
# ==========================================

def parse_event_time(text):

    now = datetime.datetime.now(tz)

    year = now.year
    month = now.month
    day = now.day
    hour = None
    minute = 0

    repeat_type = "none"
    location = ""

    # 明天
    if "明天" in text:
        dt = now + datetime.timedelta(days=1)
        year, month, day = dt.year, dt.month, dt.day

    # 後天
    if "後天" in text:
        dt = now + datetime.timedelta(days=2)
        year, month, day = dt.year, dt.month, dt.day

    # 週末
    if "週末" in text or "周末" in text:

        weekday = now.weekday()

        days_to_sat = 5 - weekday

        if days_to_sat < 0:
            days_to_sat += 7

        dt = now + datetime.timedelta(days=days_to_sat)

        year, month, day = dt.year, dt.month, dt.day

    # 每天
    if "每天" in text:
        repeat_type = "daily"

    # 每週
    if "每週" in text or "每周" in text:
        repeat_type = "weekly"

    # 解析日期
    m = re.search(r"(\d{1,2})/(\d{1,2})", text)

    if m:

        month = int(m.group(1))
        day = int(m.group(2))

    # 解析時間 10:30
    m = re.search(r"(\d{1,2}):(\d{1,2})", text)

    if m:

        hour = int(m.group(1))
        minute = int(m.group(2))

    # 解析時間 10點
    m = re.search(r"(\d{1,2})點(\d{1,2})?", text)

    if m:

        hour = int(m.group(1))

        if m.group(2):
            minute = int(m.group(2))

    if hour is None:
        return None

    dt = datetime.datetime(year, month, day, hour, minute)

    dt = tz.localize(dt)

    # 若時間已過
    if dt < now:
        dt += datetime.timedelta(days=1)

    # 地點
    if "在" in text:
        location = text.split("在")[-1]

    return dt, location, repeat_type



# ==========================================
# 新增行程
# ==========================================

def add_event(user_id, text):

    parsed = parse_event_time(text)

    if not parsed:
        return "時間解析失敗"

    dt, loc, rep = parsed

    cursor.execute(
        "INSERT INTO schedule VALUES (NULL,?,?,?,?,?)",
        (user_id, dt.isoformat(), text, loc, rep)
    )

    conn.commit()

    return f"已新增行程\n{dt.strftime('%m/%d %H:%M')}"



# ==========================================
# 行程提醒
# ==========================================

notified = set()

def check_schedule():

    now = datetime.datetime.now(tz)

    rows = cursor.execute(
        "SELECT id,user_id,time,text,repeat_type FROM schedule"
    ).fetchall()

    for r in rows:

        sid, uid, t, text, rep = r

        dt = datetime.datetime.fromisoformat(t)

        dt = tz.localize(dt)

        key = f"{sid}-{dt}"

        if abs((dt - now).total_seconds()) < 60:

            if key not in notified:

                push_message(uid, f"⏰ 行程提醒\n{text}")

                notified.add(key)

        # 重複行程
        if rep == "daily":

            while dt < now:
                dt += datetime.timedelta(days=1)

        if rep == "weekly":

            while dt < now:
                dt += datetime.timedelta(days=7)



# ==========================================
# 今日行程文字
# ==========================================

def format_today_schedule(user_id):

    events = get_today_events(user_id)

    if not events:
        return "今天沒有行程"

    return "\n".join(events)



# ==========================================
# 新聞
# ==========================================

def get_news():

    raw = web_search("台灣新聞")

    news = call_ai([
        {
            "role": "user",
            "content": f"整理3條重要新聞:\n{raw}"
        }
    ])

    return news



# ==========================================
# 早報
# ==========================================

def morning_report():

    print("執行早報")

    users = cursor.execute(
        "SELECT DISTINCT user_id FROM schedule"
    ).fetchall()

    news = get_news()

    for (uid,) in users:

        schedule_text = format_today_schedule(uid)

        msg = f"""
🌅 早安

📅 今日行程
{schedule_text}

📰 今日新聞
{news}
"""

        push_message(uid, msg)



# ==========================================
# 週報
# ==========================================

def weekly_report():

    print("執行週報")

    users = cursor.execute(
        "SELECT DISTINCT user_id FROM schedule"
    ).fetchall()

    for (uid,) in users:

        rows = cursor.execute(
            "SELECT text,time FROM schedule WHERE user_id=?",
            (uid,)
        ).fetchall()

        analysis = call_ai([
            {
                "role": "user",
                "content": f"分析使用者本週行程\n{rows}"
            }
        ])

        push_message(uid, f"📊 本週分析\n{analysis}")

# ==========================================
# 記帳系統
# ==========================================

def add_expense(user_id, amount, category, note):

    now = datetime.datetime.now(tz)

    cursor.execute(
        "INSERT INTO expenses VALUES (?,?,?,?,?)",
        (
            user_id,
            amount,
            category,
            note,
            now.isoformat()
        )
    )

    conn.commit()

    return f"已記帳 {amount} 元"


# ==========================================
# 自動分類
# ==========================================

def detect_category(text):

    food_words = ["吃", "餐", "午餐", "晚餐", "早餐", "咖啡"]

    transport_words = ["車", "捷運", "公車", "計程車"]

    shopping_words = ["買", "購物"]

    if any(w in text for w in food_words):
        return "餐飲"

    if any(w in text for w in transport_words):
        return "交通"

    if any(w in text for w in shopping_words):
        return "購物"

    return "其他"


# ==========================================
# 取得本週花費
# ==========================================

def get_week_expense(user_id):

    now = datetime.datetime.now(tz)

    week_ago = now - datetime.timedelta(days=7)

    rows = cursor.execute(
        """
        SELECT amount,category,note,time
        FROM expenses
        WHERE user_id=? AND time>?
        """,
        (
            user_id,
            week_ago.isoformat()
        )
    ).fetchall()

    return rows


# ==========================================
# 取得本月花費
# ==========================================

def get_month_expense(user_id):

    now = datetime.datetime.now(tz)

    month_ago = now - datetime.timedelta(days=30)

    rows = cursor.execute(
        """
        SELECT amount,category,note,time
        FROM expenses
        WHERE user_id=? AND time>?
        """,
        (
            user_id,
            month_ago.isoformat()
        )
    ).fetchall()

    return rows


# ==========================================
# 財務分析
# ==========================================

def finance_analysis(user_id):

    rows = get_month_expense(user_id)

    if not rows:
        return "目前沒有記帳資料"

    text = str(rows)

    result = call_ai([
        {
            "role": "system",
            "content": "你是理財顧問"
        },
        {
            "role": "user",
            "content": f"""
分析使用者花費並給建議

資料:
{text}

輸出:
1 花費趨勢
2 最大支出
3 建議
"""
        }
    ])

    return result


# ==========================================
# 支出統計
# ==========================================

def expense_summary(user_id):

    rows = get_month_expense(user_id)

    if not rows:
        return "沒有資料"

    total = 0

    categories = {}

    for amount, cat, note, t in rows:

        total += amount

        if cat not in categories:
            categories[cat] = 0

        categories[cat] += amount

    text = f"本月總花費 {total} 元\n"

    for k,v in categories.items():
        text += f"{k}: {v}\n"

    return text


# ==========================================
# 週財務報告
# ==========================================

def weekly_finance_report():

    print("執行財務週報")

    users = cursor.execute(
        "SELECT DISTINCT user_id FROM expenses"
    ).fetchall()

    for (uid,) in users:

        rows = get_week_expense(uid)

        if not rows:
            continue

        analysis = call_ai([
            {
                "role": "user",
                "content": f"""
分析本週花費

{rows}
"""
            }
        ])

        msg = f"""
💰 本週財務報告

{analysis}
"""

        push_message(uid, msg)


# ==========================================
# 記帳文字解析
# ==========================================

def parse_expense(text):

    m = re.search(r"(\d+)", text)

    if not m:
        return None

    amount = int(m.group(1))

    category = detect_category(text)

    note = text

    return amount, category, note


# ==========================================
# 記帳指令
# ==========================================

def handle_expense_command(user_id, text):

    parsed = parse_expense(text)

    if not parsed:
        return "記帳格式錯誤"

    amount, cat, note = parsed

    return add_expense(user_id, amount, cat, note)

# ==========================================
# AI 使用者人格系統
# ==========================================

def get_profile(user_id):

    row = cursor.execute(
        "SELECT summary FROM profile WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if row:
        return row[0]

    return ""


def update_profile(user_id, text):

    old = get_profile(user_id)

    try:

        summary = call_ai([
            {
                "role": "system",
                "content": "整理使用者的長期特徵，例如興趣、習慣、目標"
            },
            {
                "role": "user",
                "content": f"""
舊資料:
{old}

新訊息:
{text}

請整理新的使用者特徵
"""
            }
        ])

        cursor.execute(
            "REPLACE INTO profile VALUES (?,?)",
            (
                user_id,
                summary
            )
        )

        conn.commit()

    except Exception as e:

        print("更新profile錯誤", e)


# ==========================================
# 習慣記錄
# ==========================================

def add_habit(user_id, habit):

    cursor.execute(
        "INSERT INTO habits VALUES (?,?)",
        (
            user_id,
            habit
        )
    )

    conn.commit()

    return f"已記住習慣：{habit}"


def get_habits(user_id):

    rows = cursor.execute(
        "SELECT habit FROM habits WHERE user_id=?",
        (user_id,)
    ).fetchall()

    return [r[0] for r in rows]


# ==========================================
# 習慣分析
# ==========================================

def habit_analysis(user_id):

    habits = get_habits(user_id)

    if not habits:
        return "目前沒有習慣資料"

    result = call_ai([
        {
            "role": "system",
            "content": "你是一個生活教練"
        },
        {
            "role": "user",
            "content": f"""
使用者習慣:

{habits}

請分析生活模式並給建議
"""
        }
    ])

    return result


# ==========================================
# 自動學習習慣
# ==========================================

def detect_habit(text):

    keywords = [
        "每天",
        "習慣",
        "我都會",
        "常常"
    ]

    for k in keywords:
        if k in text:
            return True

    return False


def learn_habit(user_id, text):

    if detect_habit(text):

        add_habit(user_id, text)


# ==========================================
# 行為分析
# ==========================================

def behavior_analysis(user_id):

    messages = cursor.execute(
        """
        SELECT content
        FROM memory
        WHERE user_id=?
        ORDER BY rowid DESC
        LIMIT 50
        """,
        (user_id,)
    ).fetchall()

    if not messages:
        return "沒有資料"

    text = str(messages)

    result = call_ai([
        {
            "role": "system",
            "content": "你是生活分析師"
        },
        {
            "role": "user",
            "content": f"""
分析使用者最近行為

{text}

輸出:
1 生活模式
2 壓力狀態
3 建議
"""
        }
    ])

    return result


# ==========================================
# 目標追蹤
# ==========================================

def add_goal(user_id, goal):

    cursor.execute(
        "INSERT INTO goals VALUES (?,?)",
        (
            user_id,
            goal
        )
    )

    conn.commit()

    return f"目標已設定：{goal}"


def get_goals(user_id):

    rows = cursor.execute(
        "SELECT goal FROM goals WHERE user_id=?",
        (user_id,)
    ).fetchall()

    return [r[0] for r in rows]


# ==========================================
# 目標分析
# ==========================================

def goal_analysis(user_id):

    goals = get_goals(user_id)

    if not goals:
        return "目前沒有設定目標"

    result = call_ai([
        {
            "role": "system",
            "content": "你是目標管理教練"
        },
        {
            "role": "user",
            "content": f"""
使用者目標:

{goals}

請給達成建議
"""
        }
    ])

    return result


# ==========================================
# 智慧 AI 回覆
# ==========================================

def smart_chat(user_id, text):

    profile = get_profile(user_id)

    habits = get_habits(user_id)

    now = datetime.datetime.now(tz)

    messages = [

        {
            "role": "system",
            "content": f"""
你是使用者的私人AI助理

使用者資料:
{profile}

使用者習慣:
{habits}

現在時間:
{now}

請以助理方式回答
"""
        },

        {
            "role": "user",
            "content": text
        }

    ]

    reply = call_ai(messages)

    update_profile(user_id, text)

    learn_habit(user_id, text)

    return reply

# ============================
# Reminder System
# ============================

def add_reminder(user_id, text, remind_time):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT INTO reminders (user_id, text, remind_time)
        VALUES (?, ?, ?)
    """, (user_id, text, remind_time))

    conn.commit()
    conn.close()

def get_due_reminders():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    c.execute("""
        SELECT id, user_id, text
        FROM reminders
        WHERE remind_time <= ?
    """, (now,))

    rows = c.fetchall()
    conn.close()

    return rows

def delete_reminder(reminder_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()

# ============================
# Reminder Background Worker
# ============================

def reminder_worker():
    while True:

        reminders = get_due_reminders()

        for rid, user_id, text in reminders:

            try:
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(
                        text=f"⏰ 提醒事項\n\n{text}"
                    )
                )

                delete_reminder(rid)

            except Exception as e:
                print("Reminder error:", e)

        time.sleep(60)

threading.Thread(target=reminder_worker, daemon=True).start()

# ============================
# Daily Morning Report
# ============================

def generate_morning_report(user_id):

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT title, time
        FROM events
        WHERE user_id=? AND date=?
        ORDER BY time
    """, (user_id, today))

    events = c.fetchall()
    conn.close()

    text = "🌅 早安！今日行程\n\n"

    if not events:
        text += "今天沒有排程 👍"

    for e in events:
        text += f"• {e[1]} {e[0]}\n"

    return text

# ============================
# Morning Push Worker
# ============================

def morning_worker():

    sent_today = set()

    while True:

        now = datetime.now()

        if now.hour == 7 and now.minute == 0:

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()

            c.execute("SELECT DISTINCT user_id FROM events")
            users = c.fetchall()

            conn.close()

            for u in users:

                user_id = u[0]

                if user_id in sent_today:
                    continue

                report = generate_morning_report(user_id)

                try:
                    line_bot_api.push_message(
                        user_id,
                        TextSendMessage(text=report)
                    )

                    sent_today.add(user_id)

                except:
                    pass

        if now.hour == 7 and now.minute == 1:
            sent_today.clear()

        time.sleep(30)

threading.Thread(target=morning_worker, daemon=True).start()

# ============================
# Memory System
# ============================

def save_memory(user_id, text):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT INTO memories (user_id, text)
        VALUES (?,?)
    """, (user_id, text))

    conn.commit()
    conn.close()


def get_memories(user_id):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT text FROM memories
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 10
    """, (user_id,))

    rows = c.fetchall()
    conn.close()

    return [r[0] for r in rows]

# ============================
# AI Chat Core
# ============================

def ask_ai(user_id, message):

    memories = get_memories(user_id)

    context = "\n".join(memories)

    prompt = f"""
你是一個智慧生活助理。

使用者過去資訊：
{context}

使用者訊息：
{message}
"""

    try:

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一個聰明的生活助理"},
                {"role": "user", "content": prompt}
            ]
        )

        reply = response.choices[0].message.content

        save_memory(user_id, message)

        return reply

    except Exception as e:

        print("AI error:", e)

        return "AI暫時無法回應"

# ============================
# LINE Message Handler
# ============================

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    user_id = event.source.user_id
    text = event.message.text.strip()

    # ============================
    # 查看今日行程
    # ============================

    if text == "今天行程":

        today = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        c.execute("""
        SELECT title,time
        FROM events
        WHERE user_id=? AND date=?
        ORDER BY time
        """,(user_id,today))

        rows = c.fetchall()
        conn.close()

        if not rows:
            reply = "今天沒有行程 👍"

        else:
            reply = "📅 今日行程\n\n"
            for r in rows:
                reply += f"{r[1]} {r[0]}\n"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return


    # ============================
    # 新增提醒
    # ============================

    if text.startswith("提醒"):

        try:

            parts = text.split(" ",2)

            remind_time = parts[1]
            content = parts[2]

            add_reminder(user_id,content,remind_time)

            reply = f"⏰ 提醒已新增\n{remind_time}\n{content}"

        except:
            reply = "提醒格式錯誤\n例：提醒 2026-03-27 09:00 開會"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return


    # ============================
    # AI 對話
    # ============================

    reply = ask_ai(user_id,text)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# ============================
# Flask Webhook
# ============================

@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)

    except InvalidSignatureError:
        abort(400)

    return 'OK'

# ============================
# Render Start
# ============================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    print("AI Assistant started")

    app.run(
        host="0.0.0.0",
        port=port
    )

