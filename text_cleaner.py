import os
import re
import random
import anthropic

# ====== 設定區 ======
BLOGGER_NAME = '包子媽'
END_HASHTAG = '#開團'
# ====== 設定區結束 ======

# Claude API
client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

# 內部備註的判斷模式（這些行會被自動移除）
INTERNAL_PATTERNS = [
    r'^_{1,}\s*.*(?:到貨|通知|截單|收單)',   # __5月中左右到貨通知
    r'重要.*廠商.*收單',
    r'重要.*收單',
    r'重要.*截單',
    r'廠商.*\d+[/.-]\d+.*收單',
    r'廠商.*\d+[/.-]\d+.*截單',
    r'\d+[/.-]\d+\s*收單',
    r'\d+[/.-]\d+\s*截單',
    r'^【內部】',
    r'^內部備註',
]

# 要移除的標記
REMOVE_TAGS = [
    r'\(emoji\)',
    r'\(sticker\)',
    r'\(圖片\)',
    r'\(影片\)',
    r'\(image\)',
    r'\(video\)',
]

# ====== AI Prompt ======
SYSTEM_PROMPT = f"""你是一位專門為台灣團購社群撰寫文案的行銷達人，你的名字叫「{BLOGGER_NAME}」，目標受眾是 35–60 歲的台灣婆婆媽媽族群。

【你的寫作風格】
- 口氣像閨蜜在跟你說悄悄話，熱情、親切、有點誇張但不浮誇
- 絕對不要使用任何 emoji 或表情符號！純文字就好！
- 善用「你是不是也...」「你有沒有...」句型，直接觸碰生活痛點
- 多用感嘆號！驚嘆語氣！讓人感受到你的興奮！
- 製造稀缺感與緊迫感（限量、結單倒數、錯過可惜）
- 場景代入：讓媽媽想像這個商品出現在她生活中的畫面
- 第一人稱用「{BLOGGER_NAME}」，不要用「我」（但「我們」可以保留）

【固定文案格式】
1. 商品名稱（大字標題）
2. 結單日期（日期加結單兩個字）
3. 價格
4. 開場痛點（2–3句，引起共鳴）
5. 商品亮點（用文字條列，每點有說明）
6. 使用方式或場景描述（讓人想像用起來的感覺）
7. 注意事項（簡短條列，如果原文有的話）
8. 商品規格（重量/產地/保存/效期，如果原文有的話）
9. 結尾催單句（製造緊迫感）

【必須抓住的婆婆媽媽痛點雷達】
- 健康照顧家人：「讓全家吃得安心」「孩子搶著吃」「孝敬長輩」
- 省錢CP值：「百貨原價 xxx」「全市場最高CP值」「不怕你比較」
- 方便省事：「免解凍直接下鍋」「5分鐘上菜」「懶人也會做」
- 品質保證：「台灣製造」「嚴選食材」「幾千個回購評價」
- 稀缺限量：「限量福利品」「數量不多」「這批賣完就沒了」
- 場景描述：早餐/便當/消夜/送禮 等具體使用情境

【禁止事項】
- 不要用過於書面或生硬的語言
- 不要寫太長的大段文字，要多分段、多換行
- 不要使用任何 emoji 或表情符號
- 不要誇大醫療效果（尤其保健品類）
- 不要加 #開團 標籤（系統會自動加）
- 不要加「---」分隔線

【重要技巧】
- 段落短，每段不超過3行，方便手機閱讀
- 結尾要有強烈稀缺感，讓人覺得不買會後悔
- 絕對不要放任何 emoji、表情符號、特殊符號圖案

【範例輸出格式參考】

超好吃雞胸肉片
4/22 結單
$89／包

媽媽們～你是不是也每天煩惱便當要帶什麼？
{BLOGGER_NAME}最近發現這款雞胸肉片，真的是便當救星！

- 嚴選台灣溫體雞，急速冷凍鎖住鮮甜
- 免醃免調味，退冰直接煎就超好吃！
- 高蛋白低脂肪，健身族跟減醣族的最愛

想像一下～早上起來退冰，中午煎個3分鐘
配上白飯跟青菜，一個便當5分鐘搞定！
小包子每次看到都搶著吃，根本不夠分

每包約200g／產地台灣
冷凍保存，效期6個月

這批是工廠福利品，數量真的不多！
上次開團兩天就掃光，晚到的媽媽都在敲碗
要買要快，賣完就沒了！！"""


def force_strip_emojis(text):
    """強制移除所有 Unicode emoji。"""
    import unicodedata
    result = []
    for char in text:
        cp = ord(char)
        cat = unicodedata.category(char)
        # 跳過 emoji 相關字符
        if cat.startswith('So'):
            continue
        if (0x1F600 <= cp <= 0x1F64F or
            0x1F300 <= cp <= 0x1F5FF or
            0x1F680 <= cp <= 0x1F6FF or
            0x1F900 <= cp <= 0x1F9FF or
            0x1FA00 <= cp <= 0x1FA6F or
            0x1FA70 <= cp <= 0x1FAFF or
            0x2600 <= cp <= 0x26FF or
            0x2700 <= cp <= 0x27BF or
            0xFE00 <= cp <= 0xFE0F or
            0x200D == cp or
            0x20E3 == cp or
            0xE0020 <= cp <= 0xE007F):
            continue
        result.append(char)
    cleaned = ''.join(result)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def is_internal_line(line):
    """判斷這行是否為內部備註。"""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in INTERNAL_PATTERNS:
        if re.search(pattern, stripped):
            return True
    return False


def basic_clean(text):
    """基本清理：移除內部備註和標記。"""
    lines = text.split('\n')
    cleaned_lines = [line for line in lines if not is_internal_line(line)]
    text = '\n'.join(cleaned_lines)

    for tag_pattern in REMOVE_TAGS:
        text = re.sub(tag_pattern, '', text, flags=re.IGNORECASE)

    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def generate_copy(text, extra_instruction=None):
    """用 Claude AI 改寫文案。"""
    user_content = f'以下是要改寫的原始廠商文案：\n\n{text}'

    if extra_instruction:
        user_content += f'\n\n【額外要求】{extra_instruction}'

    try:
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_content}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f'AI generate error: {e}')
        return None


def adjust_copy(original_text, previous_result, instruction):
    """根據用戶指示調整已生成的文案。"""
    try:
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    'role': 'user',
                    'content': f'以下是要改寫的原始廠商文案：\n\n{original_text}',
                },
                {
                    'role': 'assistant',
                    'content': previous_result,
                },
                {
                    'role': 'user',
                    'content': f'請根據以下要求調整你剛才寫的文案：\n{instruction}',
                },
            ],
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f'AI adjust error: {e}')
        return None


def clean_text(text, extra_instruction=None):
    """
    主要清理函式。
    回傳清理後的文案字串。
    """
    # 基本清理
    cleaned = basic_clean(text)

    # AI 改寫
    result = generate_copy(cleaned, extra_instruction)

    if not result:
        # AI 失敗時的降級處理
        result = cleaned
        result = result.replace('我們', '\x00WOMEN\x00')
        result = result.replace('我', BLOGGER_NAME)
        result = result.replace('\x00WOMEN\x00', '我們')

    # 強制清除所有 emoji（以防 AI 還是偷加）
    result = force_strip_emojis(result)

    # 文末加標籤
    if END_HASHTAG and END_HASHTAG not in result:
        result += '\n\n' + END_HASHTAG

    return result


def adjust_text(original_text, previous_result, instruction):
    """調整已生成的文案。"""
    result = adjust_copy(original_text, previous_result, instruction)

    if not result:
        return None

    result = force_strip_emojis(result)

    if END_HASHTAG and END_HASHTAG not in result:
        result += '\n\n' + END_HASHTAG

    return result
