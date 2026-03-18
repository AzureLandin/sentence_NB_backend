import re
import json
import requests
from app.services.ai_config_service import resolve_api_config, AiConfigMissingError

# ---------------------------------------------------------------------------
# 句子分析
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """分析这个英语句子，返回JSON对象。所有内容必须用中文！

句子：{sentence}

返回格式（纯JSON，无markdown）：
{{
  "structure": [
    {{"text": "从句/短语原文", "type": "主句/定语从句/状语从句/宾语从句/短语", "translation": "该部分中文翻译"}}
  ],
  "grammar": [
    {{"point": "语法点名称", "explanation": "中文详细解释", "examples": ["相关例句"]}}
  ],
  "vocabulary": [
    {{"word": "词汇或表达", "meaning": "中文释义", "example": "例句"}}
  ],
  "translation": "通顺的中文翻译",
  "translationNote": "翻译思路分析"
}}

重要规则：
1. 所有字段内容必须用中文（type、explanation、meaning、translation、translationNote）
2. 只有 text、word、example 保留英文原文
3. 翻译要通顺自然，符合中文表达习惯
4. 语法解释要通俗易懂，适合中国学习者
5. 翻译思路要说明为什么这样翻译，做了哪些调整

仅返回JSON对象，不要解释。"""

ANALYSIS_SYSTEM_PROMPT = '你是一位专业的英语语言学教授，擅长分析英语长难句。所有回答内容必须使用中文，返回严格的JSON格式。'


def _call_ai(messages, api_config, timeout=90):
    """向第三方 AI 发起 HTTP 请求，返回文本内容。"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_config["api_key"]}',
    }
    body = {
        'model': api_config['model'],
        'messages': messages,
        'temperature': 0.3,
    }
    resp = requests.post(
        api_config['endpoint'],
        headers=headers,
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']


def analyze_sentence(user_id: str, sentence: str) -> dict:
    """
    分析英语句子，返回结构化分析结果。
    """
    api_config = resolve_api_config(user_id, 'text')

    prompt = ANALYSIS_PROMPT.replace('{sentence}', sentence.strip())
    messages = [
        {'role': 'system', 'content': ANALYSIS_SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt},
    ]

    response = _call_ai(messages, api_config)

    # 解析 JSON，去掉可能的 markdown 代码块包装
    json_str = response.strip()
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', json_str)
    if match:
        json_str = match.group(1).strip()

    analysis = json.loads(json_str)

    # 验证必要字段
    required = ('structure', 'grammar', 'vocabulary', 'translation')
    for field in required:
        if field not in analysis:
            raise ValueError(f'分析结果缺少必要字段: {field}')

    # 标准化结构，确保类型安全
    return {
        'structure': [
            {
                'text': str(item.get('text', '')),
                'type': str(item.get('type', '')),
                'translation': str(item.get('translation', '')),
            }
            for item in (analysis.get('structure') or [])
            if isinstance(item, dict)
        ],
        'grammar': [
            {
                'point': str(item.get('point', '')),
                'explanation': str(item.get('explanation', '')),
                'examples': [str(ex) for ex in (item.get('examples') or [])],
            }
            for item in (analysis.get('grammar') or [])
            if isinstance(item, dict)
        ],
        'vocabulary': [
            {
                'word': str(item.get('word', '')),
                'meaning': str(item.get('meaning', '')),
                'example': str(item.get('example', '')),
            }
            for item in (analysis.get('vocabulary') or [])
            if isinstance(item, dict)
        ],
        'translation': str(analysis.get('translation', '')),
        'translationNote': str(analysis.get('translationNote', '')),
    }


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

OCR_PROMPT = """You are an OCR assistant. Read the image and extract every English sentence as a separate item.

STEP 1 — Read all text from the image, joining text that wraps across lines into a single continuous stream.

STEP 2 — Split that stream into sentences using ONLY these terminal punctuation marks as boundaries:
  • period  .  (but NOT inside abbreviations like "Mr." or decimals like "3.14")
  • exclamation mark  !
  • question mark  ?
  A comma, semicolon, colon, or em-dash does NOT end a sentence.

STEP 3 — Return the sentences as a JSON array. Each element is one complete sentence including its terminal punctuation.

RULES:
- Keep each sentence intact; do NOT paraphrase or merge sentences.
- Fix obvious OCR errors (e.g. l→I, 0→O, rn→m).
- Skip page numbers, headers, captions, and non-English text.
- If a paragraph contains multiple sentences, output each one separately.

OUTPUT FORMAT — return ONLY the raw JSON array, no markdown, no explanation:
["Sentence one.", "Sentence two?", "Sentence three!"]

EXAMPLE:
Image text: "The quick brown fox jumps over the lazy dog. Was it fast? Yes, incredibly fast! Mr. Smith agreed."
Output: ["The quick brown fox jumps over the lazy dog.", "Was it fast?", "Yes, incredibly fast!", "Mr. Smith agreed."]

Now extract sentences from the image:"""

DEEPSEEK_OCR_PROMPT = '<image>\n<|grounding|>OCR this image.'


def _is_deepseek_ocr(model: str) -> bool:
    lower = (model or '').lower()
    return 'deepseek' in lower and 'ocr' in lower


def _is_paddle_ocr(model: str) -> bool:
    lower = (model or '').lower()
    return 'paddleocr' in lower or 'paddle-ocr' in lower


def _build_ocr_messages(base64_image: str, model: str, mime: str = 'image/jpeg') -> list:
    image_url = f'data:{mime};base64,{base64_image}'

    if _is_deepseek_ocr(model):
        return [{
            'role': 'user',
            'content': [
                {'type': 'image_url', 'image_url': {'url': image_url}},
                {'type': 'text', 'text': DEEPSEEK_OCR_PROMPT},
            ],
        }]

    if _is_paddle_ocr(model):
        return [{
            'role': 'user',
            'content': [
                {'type': 'image_url', 'image_url': {'url': image_url}},
                {'type': 'text', 'text': 'OCR this image. Extract all text.'},
            ],
        }]

    # 通用 VLM
    return [{
        'role': 'user',
        'content': [
            {'type': 'text', 'text': OCR_PROMPT},
            {'type': 'image_url', 'image_url': {'url': image_url}},
        ],
    }]


def _clean_ocr_text(text: str) -> str:
    """去除坐标标注、模型标记、HTML 标签。"""
    text = re.sub(r'\[\[\d+[\s,]+\d+[\s,]+\d+[\s,]+\d+\]\]', '', text)
    text = re.sub(r'<\|[^|]*\|>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text


def _split_text_to_sentences(text: str) -> list:
    """将 OCR 原始文本按句子边界拆分为列表。"""
    cleaned = _clean_ocr_text(text).replace('\r\n', '\n')
    lines = [l.strip() for l in cleaned.split('\n') if l.strip()]

    merged = ''
    for line in lines:
        if merged and not re.search(r'[.!?]\s*$', merged):
            merged += ' ' + line
        else:
            merged += (' ' if merged else '') + line

    merged = re.sub(r'\s+', ' ', merged).strip()
    if not merged:
        return []

    parts = re.split(r'(?<=[.!?])\s+', merged)
    result = []
    for s in parts:
        s = s.strip()
        if len(s) <= 5:
            continue
        if not re.search(r'[a-zA-Z]', s):
            continue
        result.append(s)
    return result


class NoBodiesFoundError(Exception):
    pass


def _parse_ocr_response(response: str) -> list:
    """尝试将 OCR 响应解析为句子列表；失败则回退到文本拆分。"""
    json_str = _clean_ocr_text(response).strip()

    # 去掉 markdown 代码块
    code_block = re.search(r'```(?:json)?\s*([\s\S]*?)```', json_str)
    if code_block:
        json_str = code_block.group(1).strip()

    # 尝试解析 JSON 数组
    array_match = re.search(r'\[[\s\S]*\]', json_str)
    if array_match:
        try:
            sentences = json.loads(array_match.group(0))
            if isinstance(sentences, list) and sentences:
                cleaned = [
                    re.sub(r'\s+', ' ', s).strip()
                    for s in sentences
                    if isinstance(s, str) and len(s.strip()) > 5 and re.search(r'[a-zA-Z]', s)
                ]
                if cleaned:
                    return cleaned
        except (json.JSONDecodeError, ValueError):
            pass

    # 回退：文本拆分
    sentences = _split_text_to_sentences(json_str)
    if sentences:
        return sentences

    # 检测拒绝回答
    lower = json_str.lower()
    refusal_phrases = [
        'i cannot', "i can't", "i don't see", 'no english', 'no text',
        'unable to', 'there are no', 'there is no', 'i apologize',
        '没有英文', '图片中没有', '无法识别', '未检测到', '看不到',
    ]
    if any(phrase in lower for phrase in refusal_phrases):
        raise NoBodiesFoundError('图片中未检测到英文句子')

    raise NoBodiesFoundError('图片识别结果无法解析为英文句子')


def extract_sentences(user_id: str, base64_image: str, mime: str = 'image/jpeg') -> list:
    """
    OCR 主函数：从 base64 图片中提取英文句子列表。
    """
    api_config = resolve_api_config(user_id, 'vision')
    model = api_config.get('model', '')

    messages = _build_ocr_messages(base64_image, model, mime)
    response = _call_ai(messages, api_config)

    if not response or len(response.strip()) <= 1:
        raise NoBodiesFoundError('视觉模型返回了空结果')

    return _parse_ocr_response(response)
