import re
import random

# ====== 設定區（可自行修改）======
BLOGGER_NAME = '包子媽'       # 第一人稱替換名稱
END_HASHTAG = '#開團'          # 文末自動加上的標籤
MIN_EMOJIS = 2                 # 最少插入幾個表情符號
# ====== 設定區結束 ======

# 依文案類別分組的表情符號
EMOJIS = {
    'beauty': ['✨', '💕', '🌸', '💖', '🌟', '💫', '🌺', '💗', '🪷', '💆‍♀️'],
    'food':   ['😋', '🍽️', '👍', '❤️', '🌟', '✨', '🎉', '💕', '😍', '👏'],
    'baby':   ['👶', '🍼', '💕', '✨', '🌟', '💖', '🎀', '👣', '💗', '🌸'],
    'life':   ['🏠', '💡', '✨', '❤️', '👍', '🌟', '🎉', '💕', '🙌', '💪'],
    'general': ['✨', '❤️', '🌟', '💕', '👍', '🎉', '💫', '🌸', '👏', '💖'],
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
    r'\(emoji\)',
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
    # 先保護不該替換的複合詞
    text = text.replace('我們', '\x00WOMEN\x00')
    text = text.replace('我', BLOGGER_NAME)
    text = text.replace('\x00WOMEN\x00', '我們')
    return text


def sprinkle_emojis(text, emoji_pool, count=2):
    """在適當的位置隨機插入表情符號。"""
    lines = text.split('\n')

    # 找出適合插入表情的行（非空、非標籤、有一定長度）
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
        emoji = random.choice(emoji_pool)
        lines[idx] = emoji + lines[idx]

    return '\n'.join(lines)


def clean_text(text):
    """
    主要清理函式。
    處理流程：
    1. 移除內部備註行
    2. 移除 (emoji)、(sticker) 等標記
    3. 保留 (1)、(2)、(a)、(A) 等編號
    4. 替換第一人稱
    5. 插入表情符號
    6. 文末加上 #開團
    """

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
    emoji_pool = EMOJIS.get(category, EMOJIS['general'])

    # === 3. 處理 (emoji) → 替換成隨機表情符號 ===
    def emoji_replacer(match):
        return random.choice(emoji_pool)

    text = re.sub(r'\(emoji\)', emoji_replacer, text, flags=re.IGNORECASE)

    # === 4. 移除 (sticker) 等標記，但保留 (1)(2)(a)(A) ===
    for tag_pattern in REMOVE_TAGS:
        if 'emoji' in tag_pattern:
            continue  # 已經處理過了
        text = re.sub(tag_pattern, '', text, flags=re.IGNORECASE)

    # === 5. 替換第一人稱 ===
    text = replace_pronouns(text)

    # === 6. 清理多餘空白 ===
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # === 7. 補充表情符號（如果太少） ===
    # 計算目前文案中有多少表情符號
    all_emojis = set()
    for pool in EMOJIS.values():
        all_emojis.update(pool)
    current_count = sum(1 for c in text if c in all_emojis)

    if current_count < MIN_EMOJIS:
        text = sprinkle_emojis(text, emoji_pool, MIN_EMOJIS - current_count)

    # === 8. 文末加上標籤 ===
    if END_HASHTAG and END_HASHTAG not in text:
        text += '\n\n' + END_HASHTAG

    return text
