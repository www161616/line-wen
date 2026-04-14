import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from text_cleaner import clean_text

load_dotenv()

app = Flask(__name__)

configuration = Configuration(access_token=os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])


@app.route("/callback", methods=['POST'])
def callback():
    """LINE Webhook 入口。"""
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """收到文字訊息時的處理。"""
    user_text = event.message.text

    # 說明指令
    if user_text.strip() in ('說明', '/help', '幫助'):
        help_msg = (
            '📋 文案整理機器人\n\n'
            '直接貼上廠商文案，我會幫你：\n'
            '✅ 移除內部備註（收單日、到貨通知等）\n'
            '✅ 清除 (emoji)、(sticker) 標記\n'
            '✅ 保留 (1)(2)(a)(A) 等編號\n'
            '✅ 第一人稱「我」→「包子媽」\n'
            '✅ 自動加上表情符號\n'
            '✅ 文末加上 #開團\n\n'
            '貼上文案就可以囉！'
        )
        reply_single(event, help_msg)
        return

    # 太短的訊息不處理（可能是打招呼）
    if len(user_text.strip()) < 10:
        reply_single(event, '請貼上要整理的廠商文案，我會幫你處理好 ✨')
        return

    # 清理文案
    cleaned = clean_text(user_text)

    # LINE 單則訊息上限 5000 字，超過就分段
    if len(cleaned) <= 5000:
        reply_single(event, cleaned)
    else:
        parts = split_text(cleaned, 5000)
        messages = [TextMessage(text=p) for p in parts[:5]]  # LINE 一次最多回 5 則
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages,
                )
            )


def reply_single(event, text):
    """回覆單則文字訊息。"""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def split_text(text, max_len=5000):
    """將長文案分段，盡量在換行處切割。"""
    if len(text) <= max_len:
        return [text]

    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        pos = text.rfind('\n', 0, max_len)
        if pos == -1:
            pos = max_len
        parts.append(text[:pos])
        text = text[pos:].lstrip('\n')
    return parts


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
