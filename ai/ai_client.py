import os
from openai import OpenAI


class AIClient:

    def __init__(self):

        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError("OPENROUTER_API_KEY 沒有設定")

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )

        self.model = "gpt-4o-mini"

    def chat(self, messages):

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        reply = response.choices[0].message.content

        return reply
