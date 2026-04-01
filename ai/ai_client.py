import os
import time
from openai import OpenAI


class AIClient:

    # ===== 防爆設定 =====
    DAILY_LIMIT = 300000       # 每日 token 上限
    PER_MINUTE_LIMIT = 10      # 每分鐘請求上限
    MAX_TOKENS = 800           # 每次回覆最大 token

    def __init__(self):

        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError("OPENROUTER_API_KEY 沒有設定")

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )

        self.model = "gpt-4o-mini"

        # ===== 使用統計 =====
        self.daily_tokens = 0
        self.request_times = []

    def check_limits(self):

        now = time.time()

        # ===== 清理 60 秒以前的請求 =====
        self.request_times = [
            t for t in self.request_times
            if now - t < 60
        ]

        if len(self.request_times) >= self.PER_MINUTE_LIMIT:
            raise Exception("AI 請求太快，請稍後再試")

        if self.daily_tokens >= self.DAILY_LIMIT:
            raise Exception("今日 AI 使用量已達上限")

        self.request_times.append(now)

    def chat(self, messages):

        # ===== 防爆檢查 =====
        self.check_limits()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.MAX_TOKENS
        )

        reply = response.choices[0].message.content

        # ===== 計算 token =====
        usage = response.usage

        if usage:
            total_tokens = usage.total_tokens
            self.daily_tokens += total_tokens

            print("AI tokens used:", total_tokens)
            print("Today tokens:", self.daily_tokens)

        return reply
