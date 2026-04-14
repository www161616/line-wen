import os
import traceback
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    Emoji,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from text_cleaner import clean_text

load_dotenv()

app = Flask(__name__)

configuration = Configuration(access_token=os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])


@app.route("/")
def home():
    return "LINE Bot is running!"


@app.route("/callback", methods=['POST'])
def callback():
    """LINE Webhook 入口。"""
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    app.logger.info(f'Received webhook: {body[:200]}')
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """收到文字訊息時的處理。"""
    try:
        user_text = event.message.text

        # 說明指令
        if user_text.strip() in ('說明', '/help', '幫助'):
            reply_simple(event,
                '文案整理機器人\n\n'
                '直接貼上廠商文案，我會幫你：\n'
                '- 移除內部備註（收單日、到貨通知等）\n'
                '- 清除 (emoji)、(sticker) 標記\n'
                '- 保留 (1)(2)(a)(A) 等編號\n'
                '- 第一人稱「我」→「包子媽」\n'
                '- AI 精簡到 300 字以內\n'
                '- 自動加上 LINE 表情符號\n'
                '- 文末加上 #開團\n\n'
                '貼上文案就可以囉！'
            )
            return

        # 太短的訊息不處理
        if len(user_text.strip()) < 10:
            reply_simple(event, '請貼上要整理的廠商文案，我會幫你處理好！')
            return

        # 清理文案
        cleaned, emoji_list = clean_text(user_text)

        # 建立 Emoji 物件
        if emoji_list:
            try:
                emojis = [
                    Emoji(index=e['index'], product_id=e['productId'], emoji_id=e['emojiId'])
                    for e in emoji_list
                ]
                reply_with_emoji(event, cleaned, emojis)
            except Exception as emoji_err:
                app.logger.error(f'Emoji error: {emoji_err}')
                # emoji 失敗就用純文字回覆（把 $ 移除）
                reply_simple(event, cleaned.replace('$', ''))
        else:
            reply_simple(event, cleaned)

    except Exception as e:
        app.logger.error(f'Handle message error: {traceback.format_exc()}')
        reply_simple(event, f'處理時發生錯誤，請再試一次。\n錯誤：{str(e)[:100]}')


def reply_simple(event, text):
    """回覆純文字訊息。"""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def reply_with_emoji(event, text, emojis):
    """回覆帶有 LINE emoji 的文字訊息。"""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text, emojis=emojis)],
            )
        )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
