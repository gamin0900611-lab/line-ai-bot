import os
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent
from linebot.v3.webhooks.models import TextMessageContent

from linebot.v3.messaging import (
    MessagingApi,
    Configuration,
    ApiClient,
    ReplyMessageRequest,
    TextMessage
)

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.getenv("3892ffd574c24befd128c97fc20323d4")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("1O2oOqz3rG5OkdVT2OSSQN3FyJuiFeX53iCp2UB3PbgEO93ZMlNDxRsgmcmraqmbxvj5K/x1w/HTP5a+3bVl0VIJmrKJlp5kIUKl7yylpyXzmiXpnBwumrSwYMOAs75nTY3yny5YkGD5rcmfjZRNaQdB04t89/1O/w1cDnyilFU=")

handler = WebhookHandler(LINE_CHANNEL_SECRET)

configuration = Configuration(
    access_token=LINE_CHANNEL_ACCESS_TOKEN
)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text="AI 助理已啟動")
                ]
            )
        )

# OpenRouter AI
OPENROUTER_API_KEY = os.getenv("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")

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# Webhook
@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(e)
        abort(400)

    return "OK"


# LINE 收到訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_text = event.message.text

    try:

        completion = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一個聰明的AI生活助理"},
                {"role": "user", "content": user_text}
            ]
        )

        ai_reply = completion.choices[0].message.content

    except Exception as e:

        ai_reply = "AI 發生錯誤"

        print(e)

    with ApiClient(configuration) as api_client:

        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=ai_reply)]
            )
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
