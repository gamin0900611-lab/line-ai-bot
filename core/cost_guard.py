import os
import json
import datetime


class CostGuard:

    DAILY_LIMIT = 20000  # token 限制

    def __init__(self):

        self.file = "cost_usage.json"

        if not os.path.exists(self.file):
            self.reset_usage()

    def reset_usage(self):

        data = {
            "date": str(datetime.date.today()),
            "usage": 0
        }

        with open(self.file, "w") as f:
            json.dump(data, f)

    def get_usage(self):

        with open(self.file, "r") as f:
            data = json.load(f)

        today = str(datetime.date.today())

        if data["date"] != today:
            self.reset_usage()
            return 0

        return data["usage"]

    def add_usage(self, tokens):

        with open(self.file, "r") as f:
            data = json.load(f)

        today = str(datetime.date.today())

        if data["date"] != today:
            self.reset_usage()
            data = {
                "date": today,
                "usage": 0
            }

        data["usage"] += tokens

        with open(self.file, "w") as f:
            json.dump(data, f)

    def allow_request(self, tokens):

        usage = self.get_usage()

        if usage + tokens > self.DAILY_LIMIT:
            return False

        return True
