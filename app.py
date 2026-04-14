import os
import re
import traceback
from collections import OrderedDict
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
from text_cleaner import clean_text, adjust_text

load_dotenv()

app = Flask(__name__)

configuration = Configuration(access_token=os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])


# ====== 用戶狀態記憶（對話功能）======
class UserStateCache(OrderedDict):
    """簡易 LRU 快取，記住每位用戶最後處理的文案。"""
    def __init__(self, max_size=200):
        super().__init__()
        self.max_size = max_size

    def set(self, key, value):
        if key in self:
            self.move_to_end(key)
        self[key] = value
        if len(self) > self.max_size:
            self.popitem(last=False)

    def get_state(self, key):
        if key in self:
            self.move_to_end(key)
            return self[key]
        return None


user_states = UserStateCache()


def looks_like_product_copy(text):
    """判斷文字是否像商品文案（而非對話調整指令）。"""
    if '\n' in text and len(text) > 80:
        return True
    if re.search(r'[$＄💲]\s*\d+', text):
        return True
    if len(text) > 150:
        return True
    return False


# ====== Routes ======
@app.route("/")
def home():
    return "LINE 文案整理 Bot is running!"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    app.logger.info(f'Webhook received: {body[:100]}...')
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        user_id = event.source.user_id
        user_text = event.message.text.strip()

        # === 說明指令 ===
        if user_text in ('說明', '/help', '幫助'):
            reply(event,
                '📋 文案整理機器人\n\n'
                '📝 貼上廠商文案 → 自動改寫成團購風格\n\n'
                '💬 改完之後可以直接對話調整：\n'
                '• 「長一點」「短一點」\n'
                '• 「再活潑一點」「語氣熱情一點」\n'
                '• 「加上送禮場景」\n'
                '• 「多強調CP值」\n'
                '• 「再改一次」\n\n'
                '直接貼文案就可以開始囉！✨'
            )
            return

        # === 判斷：是新文案 還是 調整指令 ===
        state = user_states.get_state(user_id)

        if state and not looks_like_product_copy(user_text):
            # 這是對話調整指令
            app.logger.info(f'Adjusting for user {user_id}: {user_text}')
            result = adjust_text(
                state['original'],
                state['result'],
                user_text,
            )
            if result:
                # 更新記憶
                state['result'] = result
                user_states.set(user_id, state)
                send_long_text(event, result)
            else:
                reply(event, '調整失敗了，請再試一次 🙏')
            return

        # === 太短的文字 ===
        if len(user_text) < 10:
            reply(event, '請貼上要整理的廠商文案，我會幫你改寫成團購風格 ✨')
            return

        # === 處理新文案 ===
        app.logger.info(f'Processing new copy for user {user_id}')
        result = clean_text(user_text)

        # 儲存狀態，讓用戶可以後續調整
        user_states.set(user_id, {
            'original': user_text,
            'result': result,
        })

        send_long_text(event, result)

    except Exception as e:
        app.logger.error(f'Error: {traceback.format_exc()}')
        reply(event, f'處理時發生錯誤 😢\n{str(e)[:200]}')


def reply(event, text):
    """回覆單則文字訊息。"""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def send_long_text(event, text):
    """回覆文字訊息，超過 5000 字自動分段。"""
    if len(text) <= 5000:
        reply(event, text)
        return

    parts = split_text(text, 5000)
    messages = [TextMessage(text=p) for p in parts[:5]]
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages,
            )
        )


def split_text(text, max_len=5000):
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
