import time
import datetime

from linebot.v3.messaging import (
    MessagingApi,
    ApiClient,
    PushMessageRequest,
    TextMessage
)


class ReminderService:

    def __init__(self, calendar_manager, configuration):

        self.calendar_manager = calendar_manager
        self.configuration = configuration
        self.running = False

    def start(self):

        print("Reminder service started")

        self.running = True

        while self.running:

            try:

                now = datetime.datetime.now()

                events = self.calendar_manager.get_all_events_global()

                for event in events:

                    event_id, user_id, title, event_time = event

                    event_dt = datetime.datetime.strptime(
                        event_time,
                        "%Y-%m-%d %H:%M"
                    )

                    # 允許1分鐘誤差
                    if now >= event_dt and now <= event_dt + datetime.timedelta(minutes=1):

                        print(f"提醒 {user_id}: {title}")

                        # ===== LINE 推播 =====

                        with ApiClient(self.configuration) as api_client:

                            line_bot_api = MessagingApi(api_client)

                            line_bot_api.push_message(
                                PushMessageRequest(
                                    to=user_id,
                                    messages=[
                                        TextMessage(
                                            text=f"🔔 行程提醒\n{title}"
                                        )
                                    ]
                                )
                            )

                # 每分鐘檢查
                time.sleep(60)

            except Exception as e:

                print("Reminder error:", e)
