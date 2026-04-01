import sqlite3


class MemoryManager:

    MAX_MEMORY_PER_USER = 200

    def __init__(self):
        self.db = "memory.db"
        self.init_db()

    # ===== 初始化資料庫 =====
    def init_db(self):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            type TEXT,
            memory TEXT
        )
        """)

        conn.commit()
        conn.close()

    # ===== 記憶過濾（防爆系統）=====
    def filter_memory(self, memory_text):

        if not memory_text:
            return None

        memory_text = memory_text.strip()

        # 太短不存
        if len(memory_text) < 4:
            return None

        blacklist = [
            "謝謝",
            "好的",
            "哈哈",
            "嗯",
            "ok",
            "OK"
        ]

        for word in blacklist:
            if word in memory_text:
                return None

        return memory_text

    # ===== 新增記憶 =====
    def add_memory(self, user_id, memory_type, memory):

        memory = self.filter_memory(memory)

        if not memory:
            return

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        # ===== 防止重複 =====
        cursor.execute(
            "SELECT memory FROM memories WHERE user_id = ?",
            (user_id,)
        )

        rows = cursor.fetchall()

        for row in rows:

            existing = row[0]

            if memory in existing or existing in memory:
                print("Memory duplicated:", memory)
                conn.close()
                return

        # ===== 存入記憶 =====
        cursor.execute(
            "INSERT INTO memories (user_id, type, memory) VALUES (?, ?, ?)",
            (user_id, memory_type, memory)
        )

        conn.commit()

        # ===== 限制記憶數量 =====
        cursor.execute(
            "SELECT id FROM memories WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        )

        rows = cursor.fetchall()

        if len(rows) > self.MAX_MEMORY_PER_USER:

            delete_ids = rows[self.MAX_MEMORY_PER_USER:]

            for row in delete_ids:
                cursor.execute(
                    "DELETE FROM memories WHERE id = ?",
                    (row[0],)
                )

            conn.commit()

        conn.close()

        print("Memory saved:", memory)

    # ===== 讀取記憶 =====
    def get_memory(self, user_id):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT type, memory FROM memories WHERE user_id = ?",
            (user_id,)
        )

        rows = cursor.fetchall()

        conn.close()

        memories = []

        for row in rows:
            memory_type = row[0]
            memory_text = row[1]

            memories.append(f"[{memory_type}] {memory_text}")

        return memories

    # ===== 查看記憶（原始資料）=====
    def get_raw_memory(self, user_id):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT type, memory FROM memories WHERE user_id = ?",
            (user_id,)
        )

        rows = cursor.fetchall()

        conn.close()

        return rows

    # ===== 清除記憶 =====
    def clear_memory(self, user_id):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM memories WHERE user_id = ?",
            (user_id,)
        )

        conn.commit()
        conn.close()

        print("All memory cleared")
