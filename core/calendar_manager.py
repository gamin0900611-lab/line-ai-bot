import sqlite3
import datetime


class CalendarManager:

    def __init__(self):

        self.db = "calendar.db"
        self.init_db()

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

    # ===== 解析時間 =====

    def parse_time(self, text):

        now = datetime.datetime.now()

        if "明天" in text:

            date = now + datetime.timedelta(days=1)

        elif "今天" in text:

            date = now

        else:

            date = now

        hour = None

        for i in range(24):

            if f"{i}點" in text or f"{i}點" in text:

                hour = i
                break

        if hour is None:
            hour = now.hour

        dt = datetime.datetime(
            date.year,
            date.month,
            date.day,
            hour,
            0
        )

        return dt.strftime("%Y-%m-%d %H:%M")
