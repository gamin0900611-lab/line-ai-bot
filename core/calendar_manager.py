import sqlite3
import datetime
import re


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

    # ===== 取得某一天行程 =====

    def get_events_by_date(self, user_id, date):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        start = f"{date} 00:00"
        end = f"{date} 23:59"

        cursor.execute(
            """
            SELECT id, title, event_time
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

    # ===== 所有行程 =====

    def get_all_events(self, user_id):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, title, event_time
            FROM events
            WHERE user_id = ?
            ORDER BY event_time
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

        conn.close()

        return rows

    # ===== 刪除行程 =====

    def delete_event(self, event_id):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM events WHERE id = ?",
            (event_id,)
        )

        conn.commit()
        conn.close()

    # ===== 解析時間（升級版） =====

    def parse_time(self, text):

        now = datetime.datetime.now()

        year = now.year
        month = now.month
        day = now.day
        hour = None
        minute = 0

        # ===== 解析 月/日 =====

        match = re.search(r"(\d{1,2})/(\d{1,2})", text)

        if match:
            month = int(match.group(1))
            day = int(match.group(2))

        # ===== 今天 / 明天 =====

        if "明天" in text:
            d = now + datetime.timedelta(days=1)
            year = d.year
            month = d.month
            day = d.day

        elif "今天" in text:
            pass

        # ===== 解析 16:30 格式 =====

        match_time = re.search(r"(\d{1,2}):(\d{1,2})", text)

        if match_time:
            hour = int(match_time.group(1))
            minute = int(match_time.group(2))

        # ===== 解析 X點 =====

        if hour is None:

            match_hour = re.search(r"(\d{1,2})點", text)

            if match_hour:
                hour = int(match_hour.group(1))

        # ===== 點半 =====

        if "點半" in text:
            minute = 30

        # ===== 點XX分 =====

        match_minute = re.search(r"點(\d{1,2})", text)

        if match_minute:
            minute = int(match_minute.group(1))

        if hour is None:
            hour = now.hour

        # ===== 上午 / 早上 =====

        if ("上午" in text or "早上" in text) and hour == 12:
            hour = 0

        # ===== 中午 =====

        if "中午" in text and hour < 11:
            hour += 12

        # ===== 下午 / 晚上 =====

        if ("下午" in text or "晚上" in text) and hour < 12:
            hour += 12

        # ===== 建立時間 =====

        dt = datetime.datetime(
            year,
            month,
            day,
            hour,
            minute
        )

        return dt.strftime("%Y-%m-%d %H:%M")
