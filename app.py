# ==========================================
# AI LINE Assistant Ultimate Version
# Part 1 / 6
# Core System + Config + Database
# ==========================================

import os
import json
import requests
import sqlite3
import datetime
import pytz
import threading
import time
from flask import Flask, request, abort

# ==========================================
# 基本設定
# ==========================================

APP_NAME = "AI Life Assistant"

TIMEZONE = "Asia/Taipei"

DAILY_LIMIT = 500

MORNING_REPORT_TIME = "05:00"

MODEL_PRIMARY = "openai/gpt-4o-mini"

MODEL_FALLBACK = "mistralai/mistral-7b-instruct"

DATABASE = "database.db"

# ==========================================
# Flask
# ==========================================

app = Flask(__name__)

# ==========================================
# Environment
# ==========================================

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("1O2oOqz3rG5OkdVT2OSSQN3FyJuiFeX53iCp2UB3PbgEO93ZMlNDxRsgmcmraqmbxvj5K/x1w/HTP5a+3bVl0VIJmrKJlp5kIUKl7yylpyXzmiXpnBwumrSwYMOAs75nTY3yny5YkGD5rcmfjZRNaQdB04t89/1O/w1cDnyilFU=")
LINE_CHANNEL_SECRET = os.getenv("3892ffd574c24befd128c97fc20323d4")
OPENROUTER_API_KEY = os.getenv("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")

# ==========================================
# Headers
# ==========================================

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

# ==========================================
# 時區
# ==========================================

tz = pytz.timezone(TIMEZONE)

# ==========================================
# Database 初始化
# ==========================================

def init_db():

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 使用者長期記憶
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profile (
        user_id TEXT PRIMARY KEY,
        summary TEXT
    )
    """)

    # 對話紀錄
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        role TEXT,
        content TEXT,
        timestamp TEXT
    )
    """)

    # 行程
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        title TEXT,
        start_time TEXT
    )
    """)

    # 記帳
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        amount INTEGER,
        category TEXT,
        note TEXT,
        time TEXT
    )
    """)

    # 使用次數限制
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usage (
        user_id TEXT,
        date TEXT,
        count INTEGER
    )
    """)

    # 目標
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        goal TEXT,
        created TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ==========================================
# DB Helper
# ==========================================

def get_conn():
    return sqlite3.connect(DATABASE)

# ==========================================
# 現在時間
# ==========================================

def now():

    return datetime.datetime.now(tz)

# ==========================================
# 今日日期
# ==========================================

def today():

    return now().strftime("%Y-%m-%d")

# ==========================================
# 現在時間字串
# ==========================================

def now_str():

    return now().strftime("%Y-%m-%d %H:%M:%S")

# ==========================================
# 使用限制檢查
# ==========================================

def check_usage(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT count FROM usage WHERE user_id=? AND date=?",
        (user_id, today())
    )

    row = cursor.fetchone()

    if row:

        if row[0] >= DAILY_LIMIT:

            conn.close()
            return False

        cursor.execute(
            "UPDATE usage SET count=count+1 WHERE user_id=? AND date=?",
            (user_id, today())
        )

    else:

        cursor.execute(
            "INSERT INTO usage VALUES (?, ?, 1)",
            (user_id, today())
        )

    conn.commit()
    conn.close()

    return True

# ==========================================
# 呼叫 AI
# ==========================================

def call_ai(messages, model=MODEL_PRIMARY):

    url = "https://openrouter.ai/api/v1/chat/completions"

    data = {
        "model": model,
        "messages": messages
    }

    try:

        r = requests.post(
            url,
            headers=HEADERS,
            json=data,
            timeout=30
        )

        res = r.json()

        return res["choices"][0]["message"]["content"]

    except Exception as e:

        print("AI錯誤:", e)

        if model != MODEL_FALLBACK:

            return call_ai(messages, MODEL_FALLBACK)

        return "AI暫時無法回應"

# ==========================================
# LINE Reply
# ==========================================

def line_reply(reply_token, text):

    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    requests.post(url, headers=headers, json=data)

# ==========================================
# LINE Push
# ==========================================

def line_push(user_id, text):

    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    requests.post(url, headers=headers, json=data)

# ==========================================
# 儲存對話
# ==========================================

def save_chat(user_id, role, content):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO chat_history (user_id,role,content,timestamp) VALUES (?,?,?,?)",
        (user_id, role, content, now_str())
    )

    conn.commit()
    conn.close()

# ==========================================
# 讀取歷史
# ==========================================

def load_history(user_id, limit=10):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role,content FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )

    rows = cursor.fetchall()

    conn.close()

    rows.reverse()

    messages = []

    for r in rows:

        messages.append({
            "role": r[0],
            "content": r[1]
        })

    return messages

# ==========================================
# 讀長期記憶
# ==========================================

def load_profile(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT summary FROM profile WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else ""

# ==========================================
# 更新長期記憶
# ==========================================

def update_profile(user_id, user_msg):

    try:

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT summary FROM profile WHERE user_id=?",
            (user_id,)
        )

        old = cursor.fetchone()

        old_summary = old[0] if old else ""

        new_summary = call_ai([
            {"role": "system", "content": "整理使用者長期特徵（習慣、目標、人格）"},
            {"role": "user", "content": old_summary + "\n" + user_msg}
        ])

        cursor.execute(
            "REPLACE INTO profile VALUES (?,?)",
            (user_id, new_summary)
        )

        conn.commit()
        conn.close()

    except Exception as e:

        print("記憶更新失敗:", e)

# ==========================================
# AI 人格
# ==========================================

AI_PERSONA = """
你是一個超級個人AI助理。

你的任務：

1 幫助使用者管理人生
2 管理行程
3 管理金錢
4 記住習慣
5 分析生活

回覆原則：

- 使用繁體中文
- 回答清楚
- 盡量簡潔
"""

# ==========================================
# 解析記帳
# ==========================================

def parse_expense(text):

    if text.startswith("記帳"):

        parts = text.split()

        if len(parts) >= 2:

            amount = int(parts[1])

            note = " ".join(parts[2:]) if len(parts) > 2 else ""

            return amount, note

    return None# 
==========================================
# 中文時間解析
# ==========================================

def parse_time(text):

    now_time = now()

    try:

        if "明天" in text:

            date = now_time + datetime.timedelta(days=1)

        elif "後天" in text:

            date = now_time + datetime.timedelta(days=2)

        elif "今天" in text:

            date = now_time

        else:

            date = now_time

        hour = None
        minute = 0

        if "點" in text:

            t = text.split("點")[0]
            nums = ''.join(filter(str.isdigit, t))

            if nums:

                hour = int(nums)

        if ":" in text:

            part = text.split(":")
            hour = int(part[0][-2:])
            minute = int(part[1][:2])

        if hour is None:

            return None

        event_time = datetime.datetime(
            date.year,
            date.month,
            date.day,
            hour,
            minute,
            tzinfo=tz
        )

        return event_time

    except Exception as e:

        print("時間解析錯誤:", e)

        return None


# ==========================================
# 新增行程
# ==========================================

def add_event(user_id, title, time):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO events (user_id,title,start_time) VALUES (?,?,?)",
        (user_id, title, time.strftime("%Y-%m-%d %H:%M:%S"))
    )

    conn.commit()
    conn.close()


# ==========================================
# 今日行程
# ==========================================

def get_today_events(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    start = today() + " 00:00:00"
    end = today() + " 23:59:59"

    cursor.execute(
        """
        SELECT title,start_time
        FROM events
        WHERE user_id=? AND start_time BETWEEN ? AND ?
        ORDER BY start_time
        """,
        (user_id, start, end)
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:

        return "今天沒有行程"

    msg = "📅 今日行程\n\n"

    for r in rows:

        msg += f"{r[1][11:16]} {r[0]}\n"

    return msg


# ==========================================
# 週末行程
# ==========================================

def get_weekend_events(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    now_time = now()

    saturday = now_time + datetime.timedelta((5-now_time.weekday())%7)
    sunday = saturday + datetime.timedelta(days=1)

    start = saturday.strftime("%Y-%m-%d") + " 00:00:00"
    end = sunday.strftime("%Y-%m-%d") + " 23:59:59"

    cursor.execute(
        """
        SELECT title,start_time
        FROM events
        WHERE user_id=? AND start_time BETWEEN ? AND ?
        ORDER BY start_time
        """,
        (user_id, start, end)
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:

        return "週末沒有行程"

    msg = "📅 週末行程\n\n"

    for r in rows:

        msg += f"{r[1]} {r[0]}\n"

    return msg


# ==========================================
# 儲存記帳
# ==========================================

def save_expense(user_id, amount, note):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO expenses
        (user_id,amount,category,note,time)
        VALUES (?,?,?,?,?)
        """,
        (user_id, amount, "general", note, now_str())
    )

    conn.commit()
    conn.close()


# ==========================================
# 今日花費
# ==========================================

def today_expense(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    start = today() + " 00:00:00"
    end = today() + " 23:59:59"

    cursor.execute(
        """
        SELECT amount,note
        FROM expenses
        WHERE user_id=? AND time BETWEEN ? AND ?
        """,
        (user_id, start, end)
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:

        return "今天沒有花費"

    total = 0

    msg = "💰 今日花費\n\n"

    for r in rows:

        total += r[0]
        msg += f"{r[0]} 元 {r[1]}\n"

    msg += f"\n合計：{total} 元"

    return msg


# ==========================================
# 財務分析
# ==========================================

def finance_analysis(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount,note FROM expenses WHERE user_id=? ORDER BY id DESC LIMIT 50",
        (user_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:

        return "沒有財務資料"

    text = ""

    for r in rows:

        text += f"{r[0]} {r[1]}\n"

    result = call_ai([
        {
            "role": "system",
            "content": "分析使用者的消費習慣"
        },
        {
            "role": "user",
            "content": text
        }
    ])

    return result


# ==========================================
# 每週報告
# ==========================================

def weekly_report(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount FROM expenses WHERE user_id=?",
        (user_id,)
    )

    rows = cursor.fetchall()

    total = sum([r[0] for r in rows]) if rows else 0

    cursor.execute(
        "SELECT COUNT(*) FROM events WHERE user_id=?",
        (user_id,)
    )

    events = cursor.fetchone()[0]

    conn.close()

    report = f"""
📊 每週生活報告

行程數量：{events}
總花費：{total} 元
"""

    return report# 
==========================================
# 讀取長期記憶
# ==========================================

def get_profile(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    try:

        cursor.execute(
            "SELECT summary FROM profile WHERE user_id=?",
            (user_id,)
        )

        row = cursor.fetchone()

        if row:
            return row[0]

        return ""

    except:

        return ""

    finally:

        conn.close()


# ==========================================
# 更新長期記憶
# ==========================================

def update_profile(user_id, user_msg):

    conn = get_conn()
    cursor = conn.cursor()

    try:

        cursor.execute(
            "SELECT summary FROM profile WHERE user_id=?",
            (user_id,)
        )

        old = cursor.fetchone()

        old_summary = old[0] if old else ""

        new_summary = call_ai([
            {
                "role": "system",
                "content": "整理使用者長期特徵，例如習慣、目標、生活模式"
            },
            {
                "role": "user",
                "content": old_summary + "\n" + user_msg
            }
        ])

        cursor.execute(
            "REPLACE INTO profile VALUES (?,?)",
            (user_id, new_summary)
        )

        conn.commit()

    except Exception as e:

        print("記憶更新錯誤:", e)

    finally:

        conn.close()


# ==========================================
# 取得最近對話
# ==========================================

def get_recent_memory(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role,content
        FROM memory
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 10
        """,
        (user_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    rows.reverse()

    messages = []

    for r in rows:

        messages.append(
            {
                "role": r[0],
                "content": r[1]
            }
        )

    return messages


# ==========================================
# 儲存對話
# ==========================================

def save_memory(user_id, role, text):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO memory
        (user_id,role,content)
        VALUES (?,?,?)
        """,
        (user_id, role, text)
    )

    conn.commit()
    conn.close()


# ==========================================
# AI 聊天
# ==========================================

def ai_chat(user_id, user_msg):

    profile = get_profile(user_id)

    history = get_recent_memory(user_id)

    messages = [
        {
            "role": "system",
            "content":
            f"""
你是一個個人AI助理。

現在時間：
{now_str()}

使用者長期資料：
{profile}

任務：
1 回答問題
2 協助規劃生活
3 管理行程
4 分析金錢
5 幫助效率
"""
        }
    ]

    messages += history

    messages.append(
        {
            "role": "user",
            "content": user_msg
        }
    )

    reply = call_ai(messages)

    return reply


# ==========================================
# 指令解析
# ==========================================

def handle_command(user_id, text):

    if text.startswith("/記帳"):

        parts = text.split()

        if len(parts) >= 2:

            amount = int(parts[1])

            note = " ".join(parts[2:]) if len(parts) > 2 else ""

            save_expense(user_id, amount, note)

            return "已記錄花費"

    if text == "/今日花費":

        return today_expense(user_id)

    if text == "/財務分析":

        return finance_analysis(user_id)

    if text == "/今日行程":

        return get_today_events(user_id)

    if text == "/週末行程":

        return get_weekend_events(user_id)

    if text == "/週報":

        return weekly_report(user_id)

    return None


# ==========================================
# AI 行程理解
# ==========================================

def ai_understand_event(user_id, text):

    prompt = f"""
判斷這句話是不是行程：

{text}

如果是，回覆：
EVENT:標題|時間

如果不是
NONE
"""

    result = call_ai([
        {"role": "user", "content": prompt}
    ])

    if "EVENT:" not in result:

        return None

    try:

        data = result.split("EVENT:")[1]

        title, time_text = data.split("|")

        event_time = parse_time(time_text)

        if event_time:

            add_event(user_id, title, event_time)

            return "已新增行程"

    except:

        pass

    return None


# ==========================================
# LINE 回覆
# ==========================================

def reply_line(reply_token, text):

    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={
            "Authorization": f"Bearer {LINE_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "replyToken": reply_token,
            "messages": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }
    )


# ==========================================
# LINE Webhook
# ==========================================

@app.route("/webhook", methods=["POST"])
def webhook():

    try:

        data = request.json

        event = data["events"][0]

        if "message" not in event:

            return "OK"

        if "text" not in event["message"]:

            return "OK"

        user_id = event["source"]["userId"]

        user_msg = event["message"]["text"]

        reply_token = event["replyToken"]

        print("User:", user_msg)

        # 存使用者訊息
        save_memory(user_id, "user", user_msg)

        # 指令系統
        cmd = handle_command(user_id, user_msg)

        if cmd:

            reply = cmd

        else:

            # AI 行程理解
            event_result = ai_understand_event(user_id, user_msg)

            if event_result:

                reply = event_result

            else:

                reply = ai_chat(user_id, user_msg)

        # 存AI回覆
        save_memory(user_id, "assistant", reply)

        # 更新長期記憶
        update_profile(user_id, user_msg)

        reply_line(reply_token, reply)

    except Exception as e:

        print("Webhook錯誤:", e)

    return "OK"# 
==========================================
# 使用次數限制
# ==========================================

DAILY_LIMIT = 500

user_usage = {}

def check_usage(user_id):

    if user_id not in user_usage:
        user_usage[user_id] = 0

    user_usage[user_id] += 1

    if user_usage[user_id] > DAILY_LIMIT:
        return False

    return True


# ==========================================
# AI 模型 fallback
# ==========================================

AI_MODELS = [
    "openai/gpt-4o-mini",
    "mistralai/mistral-7b-instruct",
    "google/gemma-7b-it"
]

current_model_index = 0


def call_ai_safe(messages):

    global current_model_index

    for i in range(len(AI_MODELS)):

        model = AI_MODELS[current_model_index]

        try:

            headers = {
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": model,
                "messages": messages
            }

            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20
            )

            data = r.json()

            reply = data["choices"][0]["message"]["content"]

            return reply

        except Exception as e:

            print("模型錯誤:", model)

            current_model_index += 1

            if current_model_index >= len(AI_MODELS):
                current_model_index = 0

    return "AI暫時忙碌"


# ==========================================
# 覆蓋原本 call_ai
# ==========================================

def call_ai(messages):

    return call_ai_safe(messages)


# ==========================================
# 每日使用量重置
# ==========================================

def reset_usage():

    global user_usage

    user_usage = {}

    print("每日使用量已重置")


# ==========================================
# 每日生活分析
# ==========================================

def daily_life_analysis(user_id):

    conn = get_conn()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role,content
        FROM memory
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 30
        """,
        (user_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    text = "\n".join([r[1] for r in rows])

    prompt = f"""
分析這個人的今天：

{text}

請回覆：

1 今日重點
2 建議改善
3 明日建議
"""

    result = call_ai([
        {"role": "user", "content": prompt}
    ])

    return result


# ==========================================
# 取得今日全部行程
# ==========================================

def get_today_all_events():

    conn = get_conn()
    cursor = conn.cursor()

    today = datetime.date.today()

    cursor.execute(
        """
        SELECT user_id,title,time
        FROM schedule
        """
    )

    rows = cursor.fetchall()

    conn.close()

    result = []

    for r in rows:

        t = datetime.datetime.fromisoformat(r[2])

        if t.date() == today:

            result.append(r)

    return result


# ==========================================
# 行程提醒
# ==========================================

def event_reminder():

    events = get_today_all_events()

    now = datetime.datetime.now()

    for user_id, title, time_str in events:

        event_time = datetime.datetime.fromisoformat(time_str)

        diff = (event_time - now).total_seconds()

        if 0 < diff < 600:

            push_line(user_id, f"提醒：{title} 即將開始")


# ==========================================
# LINE 主動推播
# ==========================================

def push_line(user_id, text):

    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "to": user_id,
            "messages": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }
    )


# ==========================================
# AI 早報
# ==========================================

def morning_report():

    conn = get_conn()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT DISTINCT user_id FROM memory"
    )

    users = cursor.fetchall()

    conn.close()

    for u in users:

        user_id = u[0]

        schedule = get_today_events(user_id)

        life = daily_life_analysis(user_id)

        prompt = f"""
現在時間：
{now_str()}

今日行程：
{schedule}

生活分析：
{life}

請生成一份 AI 早報：

1 今日重點
2 行程提醒
3 建議
"""

        report = call_ai([
            {"role": "user", "content": prompt}
        ])

        push_line(user_id, "🌅 AI早報\n\n" + report)


# ==========================================
# 排程系統
# ==========================================

def run_schedule():

    schedule.every().day.at("05:00").do(morning_report)

    schedule.every(1).minutes.do(event_reminder)

    schedule.every().day.at("00:00").do(reset_usage)

    while True:

        schedule.run_pending()

        time.sleep(1)


# ==========================================
# 啟動排程
# ==========================================

threading.Thread(target=run_schedule).start()
# ==========================================
# 每週報告
# ==========================================

def weekly_report():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT DISTINCT user_id FROM memory"
    )

    users = cursor.fetchall()

    for u in users:

        user_id = u[0]

        cursor.execute(
            """
            SELECT role,content
            FROM memory
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 100
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

        text = "\n".join([r[1] for r in rows])

        prompt = f"""
請分析這個人的一週生活：

{text}

輸出：

1 本週重點
2 進步的地方
3 需要改善
4 下週建議
"""

        report = call_ai([
            {"role": "user", "content": prompt}
        ])

        push_line(user_id, "📊 每週AI報告\n\n" + report)

    conn.close()


# ==========================================
# 財務紀錄
# ==========================================

def add_expense(user_id, text):

    try:

        parts = text.split()

        amount = int(parts[1])

        note = " ".join(parts[2:]) if len(parts) > 2 else ""

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO finance(user_id,amount,note,time)
            VALUES(?,?,?,?)
            """,
            (
                user_id,
                amount,
                note,
                now_str()
            )
        )

        conn.commit()
        conn.close()

        return "已記錄支出"

    except:

        return "格式錯誤\n/花費 100 午餐"


# ==========================================
# 財務分析
# ==========================================

def finance_analysis(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT amount,note,time
        FROM finance
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 50
        """,
        (user_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    text = "\n".join([str(r) for r in rows])

    prompt = f"""
分析這些花費：

{text}

請輸出：

1 花費習慣
2 最大支出
3 改善建議
"""

    result = call_ai([
        {"role": "user", "content": prompt}
    ])

    return result


# ==========================================
# 習慣分析
# ==========================================

def habit_learning(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT content
        FROM memory
        WHERE user_id=? AND role='user'
        ORDER BY id DESC
        LIMIT 100
        """,
        (user_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    text = "\n".join([r[0] for r in rows])

    prompt = f"""
從以下對話分析這個人的習慣：

{text}

輸出：

1 作息
2 常見目標
3 興趣
4 生活模式
"""

    habits = call_ai([
        {"role": "user", "content": prompt}
    ])

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        REPLACE INTO profile VALUES (?,?)
        """,
        (user_id, habits)
    )

    conn.commit()
    conn.close()


# ==========================================
# AI 週計畫生成
# ==========================================

def generate_week_plan(user_id):

    profile = get_profile(user_id)

    schedule_data = get_all_schedule(user_id)

    prompt = f"""
使用者資料：

{profile}

目前行程：

{schedule_data}

請生成一份週計畫：

1 健康
2 學習
3 工作
4 休息
"""

    plan = call_ai([
        {"role": "user", "content": prompt}
    ])

    return plan


# ==========================================
# AI 人格
# ==========================================

AI_PERSONA = """
你是一個個人AI助理。

角色：

1 行程管理
2 生活教練
3 學習助手
4 理財顧問

風格：

- 簡潔
- 有條理
- 提供建議
"""


# ==========================================
# AI 對話封裝
# ==========================================

def ai_chat(user_id, user_msg):

    profile = get_profile(user_id)

    messages = [

        {
            "role": "system",
            "content": AI_PERSONA
        },

        {
            "role": "system",
            "content": f"使用者資料：{profile}"
        },

        {
            "role": "system",
            "content": f"現在時間：{now_str()}"
        },

        {
            "role": "user",
            "content": user_msg
        }
    ]

    return call_ai(messages)


# ==========================================
# 指令系統
# ==========================================

def command_router(user_id, text):

    if text.startswith("/花費"):

        return add_expense(user_id, text)

    if text == "/財務":

        return finance_analysis(user_id)

    if text == "/週計畫":

        return generate_week_plan(user_id)

    if text == "/週報":

        weekly_report()

        return "已生成週報"

    return None


# ==========================================
# 每週排程
# ==========================================

def schedule_weekly_tasks():

    schedule.every().sunday.at("21:00").do(weekly_report)

    while True:

        schedule.run_pending()

        time.sleep(5)


threading.Thread(target=schedule_weekly_tasks).start()
# ==========================================
# AI 網路搜尋
# ==========================================

def ai_search(user_id, query):

    try:

        data = web_search(query)

        prompt = f"""
根據以下搜尋結果回答問題：

{data}

問題：
{query}
"""

        result = call_ai([
            {"role": "user", "content": prompt}
        ])

        return result

    except Exception as e:

        print("搜尋錯誤:", e)

        return "搜尋失敗"


# ==========================================
# Google Calendar (預留)
# ==========================================

def sync_google_calendar(user_id):

    try:

        # 這裡之後可以接 Google API
        print("Google Calendar sync placeholder")

    except Exception as e:

        print("Google calendar error:", e)


# ==========================================
# 生活儀表板
# ==========================================

def life_dashboard(user_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT text,time
        FROM schedule
        WHERE user_id=?
        ORDER BY time ASC
        LIMIT 5
        """,
        (user_id,)
    )

    events = cursor.fetchall()

    cursor.execute(
        """
        SELECT amount,note
        FROM finance
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 5
        """,
        (user_id,)
    )

    money = cursor.fetchall()

    conn.close()

    event_text = "\n".join(
        [f"{e[1]} {e[0]}" for e in events]
    ) if events else "沒有行程"

    money_text = "\n".join(
        [f"{m[0]} {m[1]}" for m in money]
    ) if money else "沒有花費"

    dashboard = f"""
📊 生活儀表板

📅 行程
{event_text}

💰 花費
{money_text}

⏰ 時間
{now_str()}
"""

    return dashboard


# ==========================================
# 錯誤保護
# ==========================================

def safe_ai_call(messages):

    try:

        return call_ai(messages)

    except Exception as e:

        print("AI錯誤:", e)

        return "AI暫時無法回覆"


# ==========================================
# 使用統計
# ==========================================

def usage_stats():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM memory
        """
    )

    msg_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM schedule
        """
    )

    event_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM finance
        """
    )

    money_count = cursor.fetchone()[0]

    conn.close()

    return f"""
📈 系統統計

對話數：
{msg_count}

行程數：
{event_count}

花費數：
{money_count}
"""


# ==========================================
# AI 自動學習排程
# ==========================================

def auto_learning():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DISTINCT user_id
        FROM memory
        """
    )

    users = cursor.fetchall()

    conn.close()

    for u in users:

        try:

            habit_learning(u[0])

        except Exception as e:

            print("習慣學習錯誤:", e)


# ==========================================
# 夜間任務
# ==========================================

def nightly_tasks():

    auto_learning()

    print("夜間任務完成")


# ==========================================
# 系統排程
# ==========================================

def start_background_jobs():

    schedule.every().day.at("03:00").do(nightly_tasks)

    schedule.every().day.at("05:00").do(morning_report)

    while True:

        schedule.run_pending()

        time.sleep(5)


threading.Thread(
    target=start_background_jobs,
    daemon=True
).start()


# ==========================================
# 擴充指令
# ==========================================

def extended_commands(user_id, text):

    if text.startswith("/查"):

        q = text.replace("/查", "")

        return ai_search(user_id, q)

    if text == "/儀表板":

        return life_dashboard(user_id)

    if text == "/統計":

        return usage_stats()

    return None


# ==========================================
# AI 回覆包裝
# ==========================================

def generate_ai_reply(user_id, user_msg):

    cmd = command_router(user_id, user_msg)

    if cmd:

        return cmd

    ext = extended_commands(user_id, user_msg)

    if ext:

        return ext

    return ai_chat(user_id, user_msg)


# ==========================================
# 系統啟動訊息
# ==========================================

print("====================================")
print(" AI LINE 助理 已啟動 ")
print(" 時區：Asia/Taipei")
print(" 每日上限：500")
print(" 早報：05:00")
print("====================================")
