import os
import re
import traceback
import unicodedata
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
from text_cleaner import clean_text, adjust_text, basic_clean, force_strip_emojis

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


def is_remove_emoji_command(text):
    """判斷是否是清除 emoji 的指令。"""
    keywords = ['清除emoji', '移除emoji', 'emoji清', '清光emoji',
                '清掉emoji', '刪除emoji', '拿掉emoji', '去掉emoji',
                '不要emoji', '清除表情', '移除表情', '表情清',
                '清光表情', '清掉表情', '刪除表情', '拿掉表情',
                '去掉表情', '不要表情', 'emoji都清', '表情都清',
                '把emoji', '把表情']
    normalized = text.lower().replace(' ', '')
    return any(kw.replace(' ', '') in normalized for kw in keywords)


def strip_emojis(text):
    """移除文字中所有的 Unicode emoji。"""
    result = []
    for char in text:
        # 保留基本標點和文字，過濾 emoji
        cat = unicodedata.category(char)
        if cat.startswith('So'):  # Symbol, Other (大部分 emoji)
            continue
        # 過濾特殊 emoji 範圍
        cp = ord(char)
        if (0x1F600 <= cp <= 0x1F64F or   # 表情
            0x1F300 <= cp <= 0x1F5FF or    # 符號圖標
            0x1F680 <= cp <= 0x1F6FF or    # 交通地圖
            0x1F900 <= cp <= 0x1F9FF or    # 補充表情
            0x1FA00 <= cp <= 0x1FA6F or    # 延伸符號
            0x1FA70 <= cp <= 0x1FAFF or    # 延伸符號B
            0x2600 <= cp <= 0x26FF or      # 雜項符號
            0x2700 <= cp <= 0x27BF or      # 裝飾符號
            0xFE00 <= cp <= 0xFE0F or      # 變體選擇符
            0x200D == cp):                  # 零寬連接符
            continue
        result.append(char)

    cleaned = ''.join(result)
    # 清理多餘空白
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def is_rewrite_command(text):
    """判斷是否是要求 AI 改寫的指令。"""
    keywords = ['改寫', '重寫', 'AI改', 'ai改', '幫我改寫', '幫我重寫',
                '用AI改', '用ai改', '改寫文案', '重寫文案']
    normalized = text.lower().replace(' ', '')
    return any(kw.replace(' ', '') in normalized for kw in keywords)


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
                '文案整理機器人\n\n'
                '直接貼上文案 → 回傳清理後的原文（去emoji、去內部備註）\n\n'
                '整理完可以接著說：\n'
                '- 「改寫」→ AI 幫你重寫成團購風格\n'
                '- 「長一點」「短一點」\n'
                '- 「再活潑一點」\n'
                '- 「加上送禮場景」\n'
                '- 「多強調CP值」\n'
                '- 任何調整需求都可以直接說\n\n'
                '貼文案就可以開始囉！'
            )
            return

        # === 取得用戶狀態 ===
        state = user_states.get_state(user_id)

        # === 「改寫」指令：用 AI 重寫上一篇 ===
        if state and is_rewrite_command(user_text):
            app.logger.info(f'AI rewrite for user {user_id}')
            result = clean_text(state['original'])
            if result:
                state['result'] = result
                user_states.set(user_id, state)
                send_long_text(event, result)
            else:
                reply(event, '改寫失敗了，請再試一次')
            return

        # === 對話調整指令 ===
        if state and not looks_like_product_copy(user_text):
            app.logger.info(f'Adjusting for user {user_id}: {user_text}')

            result = adjust_text(
                state['original'],
                state['result'],
                user_text,
            )

            if not result:
                app.logger.info('Adjust failed, falling back to regenerate')
                result = clean_text(state['original'], extra_instruction=user_text)

            if result:
                state['result'] = result
                user_states.set(user_id, state)
                send_long_text(event, result)
            else:
                reply(event, '處理失敗了，請重新貼一次文案試試')
            return

        # === 太短的文字 ===
        if len(user_text) < 10:
            reply(event, '請貼上要整理的廠商文案！')
            return

        # === 預設模式：原文清理（去 emoji、去內部備註）===
        app.logger.info(f'Basic clean for user {user_id}')
        result = basic_clean(user_text)
        result = force_strip_emojis(result)

        if '#開團' not in result:
            result += '\n\n#開團'

        # 儲存狀態，讓用戶可以後續說「改寫」或其他調整
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
