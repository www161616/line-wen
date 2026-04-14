import re
import random

# ====== 設定區（可自行修改）======
BLOGGER_NAME = '包子媽'       # 第一人稱替換名稱
END_HASHTAG = '#開團'          # 文末自動加上的標籤
MIN_EMOJIS = 2                 # 最少插入幾個 LINE emoji
# ====== 設定區結束 ======

# LINE Emoji 設定
# 完整清單：https://developers.line.biz/en/docs/messaging-api/emoji-list/
# productId 對應不同的 emoji 組合包
LINE_EMOJIS = {
    'beauty': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '005'},   # love eyes
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},   # heart
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},   # star
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},   # clap
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '008'},   # wink
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '048'},   # thumbs up
        {'productId': '5ac2197f040ab15980c9b435', 'emojiId': '018'},   # sparkle
        {'productId': '5ac2197f040ab15980c9b435', 'emojiId': '015'},   # flower
    ],
    'food': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '005'},   # love eyes
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '048'},   # thumbs up
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},   # clap
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '001'},   # smile
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},   # heart
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},   # star
    ],
    'baby': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},   # heart
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '005'},   # love eyes
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},   # star
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},   # clap
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '008'},   # wink
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '001'},   # smile
    ],
    'life': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '048'},   # thumbs up
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '001'},   # smile
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},   # clap
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},   # star
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},   # heart
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '008'},   # wink
    ],
    'general': [
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '001'},   # smile
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '005'},   # love eyes
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '069'},   # heart
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '085'},   # star
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '048'},   # thumbs up
        {'productId': '5ac1bfd5040ab15980c9b435', 'emojiId': '036'},   # clap
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

# 要完整移除的標記（不分大小寫）
REMOVE_TAGS = [
    r'\(sticker\)',
    r'\(圖片\)',
    r'\(影片\)',
    r'\(image\)',
    r'\(video\)',
]


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


def replace_pronouns(text):
    """將第一人稱「我」替換成部落客名稱，但保留「我們」。"""
    text = text.replace('我們', '\x00WOMEN\x00')
    text = text.replace('我', BLOGGER_NAME)
    text = text.replace('\x00WOMEN\x00', '我們')
    return text


def sprinkle_emoji_placeholders(text, count=2):
    """在適當的位置插入 $ 佔位符（給 LINE emoji 用）。"""
    lines = text.split('\n')

    candidates = [
        i for i, line in enumerate(lines)
        if line.strip()
        and not line.strip().startswith('#')
        and not line.strip().startswith('$')
        and len(line.strip()) > 5
    ]

    if not candidates:
        return text

    selected = random.sample(candidates, min(count, len(candidates)))
    for idx in selected:
        lines[idx] = '$' + lines[idx]

    return '\n'.join(lines)


def build_emoji_list(text, category):
    """根據 $ 佔位符的位置，建立 LINE emoji 資料列表。"""
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

    return emojis


def clean_text(text):
    """
    主要清理函式。
    回傳 (cleaned_text, emoji_list)
    - cleaned_text: 清理後的文字，LINE emoji 位置用 $ 標記
    - emoji_list: LINE emoji 資料列表（給 TextMessage 的 emojis 參數用）
    """

    # === 0. 先把原文中的 $ 替換成全形，避免衝突 ===
    text = text.replace('$', '＄')

    # === 1. 移除內部備註行 ===
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if is_internal_line(line):
            continue
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # === 2. 偵測文案類別 ===
    category = detect_category(text)

    # === 3. 處理 (emoji) → 替換成 $ 佔位符 ===
    text = re.sub(r'\(emoji\)', '$', text, flags=re.IGNORECASE)

    # === 4. 移除 (sticker) 等標記，但保留 (1)(2)(a)(A) ===
    for tag_pattern in REMOVE_TAGS:
        text = re.sub(tag_pattern, '', text, flags=re.IGNORECASE)

    # === 5. 替換第一人稱 ===
    text = replace_pronouns(text)

    # === 6. 清理多餘空白 ===
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # === 7. 補充 emoji 佔位符（如果太少） ===
    current_count = text.count('$')
    if current_count < MIN_EMOJIS:
        text = sprinkle_emoji_placeholders(text, MIN_EMOJIS - current_count)

    # === 8. 文末加上標籤 ===
    if END_HASHTAG and END_HASHTAG not in text:
        text += '\n\n' + END_HASHTAG

    # === 9. 建立 LINE emoji 資料 ===
    emoji_list = build_emoji_list(text, category)

    return text, emoji_list
