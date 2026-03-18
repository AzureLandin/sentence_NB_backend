"""导入初始每日一句数据"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from app import create_app
from app.models import db, DailySentence

SAMPLE_SENTENCES = [
    {
        'content': 'The scientist who discovered the cure had been working on it for decades.',
        'translation': '发现这种疗法的科学家已经为此工作了几十年。',
        'grammar_point': '定语从句',
    },
    {
        'content': 'Had I known about the meeting, I would have attended.',
        'translation': '如果我知道那个会议，我就参加了。',
        'grammar_point': '虚拟语气',
    },
    {
        'content': 'The book which you lent me was fascinating.',
        'translation': '你借给我的那本书很迷人。',
        'grammar_point': '定语从句',
    },
    {
        'content': 'It is essential that he be informed immediately.',
        'translation': '他必须立即被通知。',
        'grammar_point': '虚拟语气',
    },
    {
        'content': 'The more you practice, the better you become.',
        'translation': '你练习得越多，就变得越好。',
        'grammar_point': '比较结构',
    },
    {
        'content': 'Not only did she win the competition, but she also broke the record.',
        'translation': '她不仅赢得了比赛，还打破了纪录。',
        'grammar_point': '倒装句',
    },
    {
        'content': 'The reason why he failed is that he didn\'t study hard enough.',
        'translation': '他失败的原因是他学习不够努力。',
        'grammar_point': '定语从句',
    },
    {
        'content': 'Were I in your position, I would accept the offer.',
        'translation': '如果我是你的处境，我会接受这个提议。',
        'grammar_point': '虚拟语气倒装',
    },
    {
        'content': 'What surprised me most was his attitude towards the problem.',
        'translation': '最让我惊讶的是他对这个问题的态度。',
        'grammar_point': '主语从句',
    },
    {
        'content': 'The teacher suggested that he study harder for the exam.',
        'translation': '老师建议他更努力地为考试学习。',
        'grammar_point': '虚拟语气',
    },
    {
        'content': 'Only when the rain stopped could we continue our journey.',
        'translation': '只有当雨停了，我们才能继续我们的旅程。',
        'grammar_point': '倒装句',
    },
    {
        'content': 'The man whose car was stolen reported it to the police.',
        'translation': '车被偷的那个人向警察报了案。',
        'grammar_point': '定语从句',
    },
    {
        'content': 'It is said that he has written several novels.',
        'translation': '据说他已经写了几部小说。',
        'grammar_point': '被动语态',
    },
    {
        'content': 'However difficult the task may be, we must complete it.',
        'translation': '无论任务多么困难，我们都必须完成它。',
        'grammar_point': '让步状语从句',
    },
    {
        'content': 'The proposal that a new library be built was rejected.',
        'translation': '建造新图书馆的提议被拒绝了。',
        'grammar_point': '同位语从句',
    },
    {
        'content': 'So fast did he run that nobody could catch him.',
        'translation': '他跑得太快了，没人能追上他。',
        'grammar_point': '倒装句',
    },
    {
        'content': 'I wish I had studied harder when I was young.',
        'translation': '我希望我年轻时学习更努力。',
        'grammar_point': '虚拟语气',
    },
    {
        'content': 'The fact that he is innocent proves nothing.',
        'translation': '他是无辜的这一事实证明不了什么。',
        'grammar_point': '同位语从句',
    },
    {
        'content': 'Little did we know what would happen next.',
        'translation': '我们几乎不知道接下来会发生什么。',
        'grammar_point': '倒装句',
    },
    {
        'content': 'It is time that we took action to protect the environment.',
        'translation': '是我们采取行动保护环境的时候了。',
        'grammar_point': '虚拟语气',
    },
    {
        'content': 'The more careful you are, the fewer mistakes you will make.',
        'translation': '你越仔细，犯的错误就越少。',
        'grammar_point': '比较结构',
    },
    {
        'content': 'Had it not been for your help, I would have failed.',
        'translation': '如果不是你的帮助，我就失败了。',
        'grammar_point': '虚拟语气',
    },
    {
        'content': 'What matters most is not what you say but what you do.',
        'translation': '最重要的不是你说什么，而是你做什么。',
        'grammar_point': '主语从句',
    },
    {
        'content': 'Never have I seen such a beautiful sunset.',
        'translation': '我从未见过如此美丽的日落。',
        'grammar_point': '倒装句',
    },
    {
        'content': 'The problem lies in that we lack sufficient funds.',
        'translation': '问题在于我们缺乏足够的资金。',
        'grammar_point': '表语从句',
    },
    {
        'content': 'It is important that everyone understand the rules.',
        'translation': '每个人都理解规则是很重要的。',
        'grammar_point': '虚拟语气',
    },
    {
        'content': 'Where there is a will, there is a way.',
        'translation': '有志者事竟成。',
        'grammar_point': '地点状语从句',
    },
    {
        'content': 'The house which stands on the hill belongs to my uncle.',
        'translation': '矗立在山上的那座房子属于我叔叔。',
        'grammar_point': '定语从句',
    },
    {
        'content': 'Not until he arrived did the meeting begin.',
        'translation': '直到他到达，会议才开始。',
        'grammar_point': '倒装句',
    },
    {
        'content': 'Whatever you do, do it with all your heart.',
        'translation': '无论你做什么，都要全心全意地做。',
        'grammar_point': '让步状语从句',
    },
]


def seed_sentences(days=30):
    app = create_app()
    with app.app_context():
        today = date.today()
        count = 0
        for i, sentence_data in enumerate(SAMPLE_SENTENCES[:days]):
            target_date = today + timedelta(days=i)
            existing = DailySentence.query.filter_by(date=target_date).first()
            if not existing:
                sentence = DailySentence(
                    content=sentence_data['content'],
                    translation=sentence_data['translation'],
                    grammar_point=sentence_data.get('grammar_point'),
                    date=target_date,
                )
                db.session.add(sentence)
                count += 1
        db.session.commit()
        print(f'已填充 {count} 条每日一句')


if __name__ == '__main__':
    seed_sentences()