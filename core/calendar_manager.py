import sqlite3
import datetime


class CalendarManager:

    def __init__(self):

        self.db = "calendar.db"
        self.init_db()

    # ===== 初始化資料庫 =====

    def init_db(self):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            title TEXT,
            event_time TEXT
        )
        """)

        conn.commit()
        conn.close()

    # ===== 新增行程 =====

    def add_event(self, user_id, title, event_time):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO events (user_id, title, event_time) VALUES (?, ?, ?)",
            (user_id, title, event_time)
        )

        conn.commit()
        conn.close()

    # ===== 取得某一天 =====

    def get_events_by_date(self, user_id, date):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        start = f"{date} 00:00"
        end = f"{date} 23:59"

        cursor.execute(
            """
            SELECT title, event_time
            FROM events
            WHERE user_id = ?
            AND event_time BETWEEN ? AND ?
            ORDER BY event_time
            """,
            (user_id, start, end)
        )

        rows = cursor.fetchall()

        conn.close()

        return rows

    # ===== 取得全部 =====

    def get_all_events(self, user_id):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT title, event_time
            FROM events
            WHERE user_id = ?
            ORDER BY event_time
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

        conn.close()

        return rows

    # ===== 解析自然語言時間 =====

    def parse_time(self, text):

        now = datetime.datetime.now()

        # ===== 日期 =====

        if "明天" in text:
            date = now + datetime.timedelta(days=1)

        elif "今天" in text:
            date = now

        else:
            date = now

        # ===== 小時 =====

        hour = None

        for i in range(24):

            if f"{i}點" in text:
                hour = i
                break

        if hour is None:
            hour = now.hour

        # ===== 晚上 / 下午 =====

        if ("晚上" in text or "下午" in text) and hour < 12:
            hour += 12

        # ===== 分鐘 =====

        minute = 0

        if "30分" in text or "半" in text:
            minute = 30

        # ===== 建立時間 =====

        dt = datetime.datetime(
            date.year,
            date.month,
            date.day,
            hour,
            minute
        )

        return dt.strftime("%Y-%m-%d %H:%M")
