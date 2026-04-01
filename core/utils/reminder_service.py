import time
import datetime


class ReminderService:

    def __init__(self, calendar_manager):
        self.calendar_manager = calendar_manager
        self.running = False

    def start(self):

        print("Reminder service started")

        self.running = True

        while self.running:

            try:

                now = datetime.datetime.now()
                now_str = now.strftime("%Y-%m-%d %H:%M")

                # 取得所有行程
                events = self.calendar_manager.get_all_events_global()

                for event in events:

                    event_id, user_id, title, event_time = event

                    if event_time == now_str:

                        print(f"提醒 {user_id}: {title}")

                        # 這裡之後可以接 LINE push message

                time.sleep(60)

            except Exception as e:

                print("Reminder error:", e)
