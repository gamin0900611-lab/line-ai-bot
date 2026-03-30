import sqlite3


class MemoryManager:

    def __init__(self):

        self.db = "memory.db"
        self.init_db()

    def init_db(self):

        conn = sqlite3.connect(self.db)
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

    def save_memory(self, user_id, memory):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO memories (user_id, memory) VALUES (?, ?)",
            (user_id, memory)
        )

        conn.commit()
        conn.close()

    def get_memory(self, user_id):

        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT memory FROM memories WHERE user_id = ?",
            (user_id,)
        )

        rows = cursor.fetchall()

        conn.close()

        memories = [row[0] for row in rows]

        return memories
