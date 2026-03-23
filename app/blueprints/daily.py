import uuid
import random
import requests
from flask import Blueprint, jsonify
from datetime import date
from sqlalchemy.exc import IntegrityError
from app.models import db, DailySentence

daily_bp = Blueprint("daily", __name__, url_prefix="/daily")

ZENQUOTES_API = "https://zenquotes.io/api/today"

# 内置备用句子库，当外部 API 不可用时（如境外 API 在云托管中被屏蔽）使用。
# 以日期序号取模，保证同一天始终返回同一条句子。
FALLBACK_SENTENCES = [
    {
        "content": "The only way to do great work is to love what you do.",
        "author": "Steve Jobs",
    },
    {
        "content": "In the middle of every difficulty lies opportunity.",
        "author": "Albert Einstein",
    },
    {
        "content": "It does not matter how slowly you go as long as you do not stop.",
        "author": "Confucius",
    },
    {
        "content": "Life is what happens when you are busy making other plans.",
        "author": "John Lennon",
    },
    {
        "content": "The future belongs to those who believe in the beauty of their dreams.",
        "author": "Eleanor Roosevelt",
    },
    {
        "content": "Spread love everywhere you go. Let no one ever come to you without leaving happier.",
        "author": "Mother Teresa",
    },
    {
        "content": "When you reach the end of your rope, tie a knot in it and hang on.",
        "author": "Franklin D. Roosevelt",
    },
    {
        "content": "Always remember that you are absolutely unique. Just like everyone else.",
        "author": "Margaret Mead",
    },
    {
        "content": "Do not go where the path may lead; go instead where there is no path and leave a trail.",
        "author": "Ralph Waldo Emerson",
    },
    {
        "content": "You will face many defeats in life, but never let yourself be defeated.",
        "author": "Maya Angelou",
    },
    {
        "content": "The greatest glory in living lies not in never falling, but in rising every time we fall.",
        "author": "Nelson Mandela",
    },
    {
        "content": "In the end, it is not the years in your life that count. It is the life in your years.",
        "author": "Abraham Lincoln",
    },
    {
        "content": "Never let the fear of striking out keep you from playing the game.",
        "author": "Babe Ruth",
    },
    {
        "content": "Life is either a daring adventure or nothing at all.",
        "author": "Helen Keller",
    },
    {
        "content": "Many of life's failures are people who did not realize how close they were to success when they gave up.",
        "author": "Thomas A. Edison",
    },
    {
        "content": "You have brains in your head. You have feet in your shoes. You can steer yourself any direction you choose.",
        "author": "Dr. Seuss",
    },
    {
        "content": "If life were predictable it would cease to be life, and be without flavor.",
        "author": "Eleanor Roosevelt",
    },
    {
        "content": "If you look at what you have in life, you will always have more.",
        "author": "Oprah Winfrey",
    },
    {
        "content": "If you set your goals ridiculously high and it's a failure, you will fail above everyone else's success.",
        "author": "James Cameron",
    },
    {
        "content": "Life is not measured by the number of breaths we take, but by the moments that take our breath away.",
        "author": "Maya Angelou",
    },
    {
        "content": "If you want to live a happy life, tie it to a goal, not to people or things.",
        "author": "Albert Einstein",
    },
    {
        "content": "Believe you can and you're halfway there.",
        "author": "Theodore Roosevelt",
    },
    {
        "content": "Money and success don't change people; they merely amplify what is already there.",
        "author": "Will Smith",
    },
    {
        "content": "Your time is limited, so don't waste it living someone else's life.",
        "author": "Steve Jobs",
    },
    {
        "content": "Not how long, but how well you have lived is the main thing.",
        "author": "Seneca",
    },
    {
        "content": "Act as if what you do makes a difference. It does.",
        "author": "William James",
    },
    {
        "content": "The way to get started is to quit talking and begin doing.",
        "author": "Walt Disney",
    },
    {
        "content": "Don't let yesterday take up too much of today.",
        "author": "Will Rogers",
    },
    {
        "content": "You learn more from failure than from success. Don't let it stop you.",
        "author": "Unknown",
    },
    {
        "content": "It's not whether you get knocked down, it's whether you get up.",
        "author": "Vince Lombardi",
    },
]


def success_response(data=None, message="success"):
    return jsonify(
        {
            "code": "OK",
            "message": message,
            "data": data or {},
            "requestId": str(uuid.uuid4()),
        }
    )


def error_response(message, error_code, status=400):
    return (
        jsonify(
            {
                "code": "ERROR",
                "message": message,
                "errorCode": error_code,
                "retryable": False,
                "details": {},
                "requestId": str(uuid.uuid4()),
            }
        ),
        status,
    )


def fetch_zenquotes():
    """尝试从 ZenQuotes 获取今日句子，失败时返回 None。"""
    try:
        resp = requests.get(ZENQUOTES_API, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data and len(data) > 0:
            quote = data[0]
            return {
                "content": quote.get("q", ""),
                "author": quote.get("a", "Unknown"),
            }
    except Exception:
        pass
    return None


def get_fallback_sentence(today: date) -> dict:
    """根据日期确定性地从内置库中取一条句子，同一天始终返回同一条。"""
    index = today.toordinal() % len(FALLBACK_SENTENCES)
    return FALLBACK_SENTENCES[index]


@daily_bp.route("/sentence", methods=["GET"])
def get_daily_sentence():
    today = date.today()

    # 查询今日缓存
    try:
        sentence = DailySentence.query.filter_by(date=today).first()
    except Exception:
        return error_response("服务暂时不可用", "SERVICE_UNAVAILABLE", 503)

    if sentence:
        return success_response(sentence.to_dict())

    # 优先尝试 ZenQuotes，不可用时降级到内置句子库
    quote = fetch_zenquotes() or get_fallback_sentence(today)

    try:
        sentence = DailySentence(
            content=quote["content"],
            translation=quote['author'],
            grammar_point=None,
            date=today,
        )
        db.session.add(sentence)
        db.session.commit()
    except IntegrityError:
        # 多实例并发写入同一天数据时触发 UNIQUE 冲突，直接读取已存在的记录
        db.session.rollback()
        sentence = DailySentence.query.filter_by(date=today).first()
        if sentence:
            return success_response(sentence.to_dict())
        return error_response("服务暂时不可用", "SERVICE_UNAVAILABLE", 503)
    except Exception:
        db.session.rollback()
        return error_response("服务暂时不可用", "SERVICE_UNAVAILABLE", 503)

    return success_response(sentence.to_dict())
