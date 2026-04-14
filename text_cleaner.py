import os
import re
import random
import anthropic

# ====== 設定區（可自行修改）======
BLOGGER_NAME = '包子媽'       # 第一人稱替換名稱
END_HASHTAG = '#開團'          # 文末自動加上的標籤
MIN_EMOJIS = 3                 # 最少插入幾個 LINE emoji
MAX_CHARS = 300                # 文案精簡目標字數
# ====== 設定區結束 ======

# LINE Emoji 設定
# 完整清單：https://developers.line.biz/en/docs/messaging-api/emoji-list/
LINE_EMOJIS = {
    'beauty': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '005'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '008'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '048'},
        {'productId': '5ac2197f040ab15980c9b435', 'emojiId': '018'},
        {'productId': '5ac2197f040ab15980c9b435', 'emojiId': '015'},
    ],
    'food': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '005'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '048'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '001'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},
    ],
    'baby': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '005'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '008'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '001'},
    ],
    'life': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '048'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '001'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '008'},
    ],
    'general': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '001'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '005'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '048'},
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},
    ],
}

# 關鍵字對應類別
CATEGORY_KEYWORDS = {
    'beauty': [
        '保養', '美白', '精華', '面膜', '乳液', '護膚', '修復', '舒緩',
        '肌膚', '防曬', '卸妝', '化妝水', '眼霜', '面霜', '清潔', '洗面',
        '去角質', '抗老', '緊緻', '保濕', '冷感', '能量', '修護', '敏感肌',
        '控油', '美容', '霜', '精華液', '安瓶', '凝膠', '凝露',
    ],
    'food': [
        '美食', '零食', '好吃', '料理', '食品', '點心', '餅乾', '巧克力',
        '甜點', '蛋糕', '麵包', '咖啡', '茶', '飲品', '調味', '醬料',
        '有機', '營養', '沖泡', '果乾', '堅果', '即食',
    ],
    'baby': [
        '寶寶', '嬰兒', '奶粉', '尿布', '副食品', '兒童', '親子',
        '哺乳', '育兒', '玩具', '幼兒', '奶瓶', '推車', '安撫',
    ],
    'life': [
        '居家', '收納', '清潔劑', '洗衣', '廚房', '家電', '生活',
        '除臭', '芳香', '擴香', '洗碗', '拖把',
    ],
}

# 內部備註的判斷模式（這些行會被自動移除）
INTERNAL_PATTERNS = [
    r'重要.*廠商.*收單',
    r'重要.*收單',
    r'重要.*截單',
    r'廠商.*\d+[/.-]\d+.*收單',
    r'廠商.*\d+[/.-]\d+.*截單',
    r'\d+[/.-]\d+\s*收單',
    r'\d+[/.-]\d+\s*截單',
    r'_{3,}.*(?:到貨|通知|截單|收單)',
    r'^【內部】',
    r'^內部備註',
]

# 要完整移除的標記
REMOVE_TAGS = [
    r'\(emoji\)',
    r'\(sticker\)',
    r'\(圖片\)',
    r'\(影片\)',
    r'\(image\)',
    r'\(video\)',
]

# Claude API client
client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

SUMMARIZE_PROMPT = f"""你是「{BLOGGER_NAME}」的文案助手，負責把廠商提供的商品文案精簡整理。

請遵守以下規則：
1. 精簡到 {MAX_CHARS} 字以內（不含標點符號計算可以稍微寬鬆）
2. 保留：商品名稱、價格、預購/到貨資訊
3. 用「{BLOGGER_NAME}」的口吻重寫，語氣要生活化、親切，像是自己用過在推薦給朋友
4. 第一人稱用「{BLOGGER_NAME}」，不要用「我」
5. 保留重點賣點，去掉重複和過度描述
6. 不要加 (emoji) 標記，不要加任何表情符號
7. 不要加 #開團 標籤（系統會自動加）
8. 不要加「---」分隔線
9. 如果原文有使用步驟，精簡成一句話帶過即可
10. 段落之間用一個空行分隔"""


def detect_category(text):
    """根據文案內容偵測商品類別。"""
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'general'


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
    # 移除內部備註行
    lines = text.split('\n')
    cleaned_lines = [line for line in lines if not is_internal_line(line)]
    text = '\n'.join(cleaned_lines)

    # 移除標記
    for tag_pattern in REMOVE_TAGS:
        text = re.sub(tag_pattern, '', text, flags=re.IGNORECASE)

    # 清理空白
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def summarize_with_ai(text):
    """用 Claude AI 精簡文案到指定字數。"""
    try:
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1024,
            messages=[
                {
                    'role': 'user',
                    'content': f'{SUMMARIZE_PROMPT}\n\n以下是要整理的原始文案：\n\n{text}',
                }
            ],
        )
        return message.content[0].text.strip()
    except Exception as e:
        # AI 失敗時回退到基本清理
        print(f'AI summarize error: {e}')
        return None


def add_line_emojis(text, category):
    """在文字中插入 $ 佔位符並建立 LINE emoji 資料。"""
    # 先把原文中的 $ 替換成全形
    text = text.replace('$', '＄')

    # 找適合插入的位置（非空行開頭）
    lines = text.split('\n')
    candidates = [
        i for i, line in enumerate(lines)
        if line.strip()
        and not line.strip().startswith('#')
        and len(line.strip()) > 3
    ]

    if candidates:
        count = min(MIN_EMOJIS, len(candidates))
        selected = random.sample(candidates, count)
        for idx in selected:
            lines[idx] = '$' + lines[idx]

    text = '\n'.join(lines)

    # 建立 emoji 資料
    emoji_pool = LINE_EMOJIS.get(category, LINE_EMOJIS['general'])
    emojis = []
    for i, char in enumerate(text):
        if char == '$':
            emoji_data = random.choice(emoji_pool)
            emojis.append({
                'index': i,
                'productId': emoji_data['productId'],
                'emojiId': emoji_data['emojiId'],
            })

    return text, emojis


def clean_text(text):
    """
    主要清理函式。
    回傳 (cleaned_text, emoji_list)
    """

    # === 1. 基本清理 ===
    cleaned = basic_clean(text)

    # === 2. 偵測類別 ===
    category = detect_category(cleaned)

    # === 3. AI 精簡文案 ===
    summarized = summarize_with_ai(cleaned)
    if summarized:
        result = summarized
    else:
        # AI 失敗，用基本清理結果
        result = cleaned
        # 替換第一人稱
        result = result.replace('我們', '\x00WOMEN\x00')
        result = result.replace('我', BLOGGER_NAME)
        result = result.replace('\x00WOMEN\x00', '我們')

    # === 4. 文末加標籤 ===
    if END_HASHTAG and END_HASHTAG not in result:
        result += '\n\n' + END_HASHTAG

    # === 5. 加入 LINE emoji ===
    result, emoji_list = add_line_emojis(result, category)

    return result, emoji_list
