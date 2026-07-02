#!/usr/bin/env python3
"""
多语言分词器 — 自动检测语言并调用对应分词引擎

支持: 中文(jieba) / 日文(fugashi) / 韩文(规则) / 希伯来文(hebrew_tokenizer) / 英文及拉丁语系(空格)
"""
import re
from collections import Counter

# 懒加载分词器
_jieba = None
_tagger = None
_he_tokenizer_func = None

# 韩文语尾表
_KOREAN_ENDINGS = sorted([
    '입니다', '합니다', '습니다', '세요', '니까',
    '은', '는', '이', '가', '을', '를', '의', '에', '도',
    '와', '과', '으로', '로', '에서', '부터', '까지', '마다',
    '이라', '라', '이야', '야', '이에요', '예요',
], key=len, reverse=True)


def _get_jieba():
    global _jieba
    if _jieba is None:
        import jieba
        _jieba = jieba
    return _jieba


def _get_tagger():
    global _tagger
    if _tagger is None:
        from fugashi import Tagger
        _tagger = Tagger('-Owakati')
    return _tagger


def _get_he_tokenizer():
    global _he_tokenizer_func
    if _he_tokenizer_func is None:
        from hebrew_tokenizer import tokenize as he_tok
        _he_tokenizer_func = he_tok
    return _he_tokenizer_func


def detect_lang(text):
    """检测文本主要语言"""
    sample = text[:500]
    
    ja_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', sample))
    ko_chars = len(re.findall(r'[\uAC00-\uD7AF]', sample))
    zh_chars = len(re.findall(r'[\u4E00-\u9FFF]', sample))
    he_chars = len(re.findall(r'[\u0590-\u05FF]', sample))
    latin_chars = len(re.findall(r'[a-zA-Z]', sample))
    
    if he_chars > 0:
        return 'he'
    if ja_chars > zh_chars and ja_chars > 0:
        return 'ja'
    if ko_chars > 0:
        return 'ko'
    if zh_chars > 0:
        return 'zh'
    return 'en' if latin_chars > 0 else 'en'


def tokenize(text):
    """通用分词 — 自动检测语言"""
    lang = detect_lang(text)
    return _tokenize_by_lang(text, lang)


def tokenize_with_lang(text, lang):
    """指定语言分词"""
    return _tokenize_by_lang(text, lang)


def _tokenize_by_lang(text, lang):
    if lang == 'zh':
        jieba = _get_jieba()
        return ' '.join(jieba.cut(text))
    elif lang == 'ja':
        tagger = _get_tagger()
        return tagger.parse(text).strip()
    elif lang == 'ko':
        return _tokenize_ko(text)
    elif lang == 'he':
        return _tokenize_he(text)
    else:
        return text


def _tokenize_ko(text):
    """韩文分词"""
    tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text)
    cleaned = []
    for t in tokens:
        for e in _KOREAN_ENDINGS:
            if t.endswith(e) and len(t) > len(e):
                t = t[:-len(e)]
                break
        cleaned.append(t)
    return ' '.join(cleaned)


def _tokenize_he(text):
    """希伯来文分词"""
    tokenizer = _get_he_tokenizer()
    tokens = []
    for token_type, token, start, end in tokenizer(text):
        tokens.append(token)
    return ' '.join(tokens)


def extract_keywords(text, topK=20):
    """通用关键词提取"""
    lang = detect_lang(text)
    
    if lang == 'zh':
        import jieba.analyse
        return jieba.analyse.textrank(text, topK=topK)
    
    elif lang in ('ja', 'ko', 'he'):
        # 基于词频
        words = _tokenize_by_lang(text, lang).split()
        return [w for w, _ in Counter(words).most_common(topK)]
    
    else:
        # 英文：过滤短词后按词频
        words = re.findall(r'[a-zA-Z]{3,}', text.lower())
        return [w for w, _ in Counter(words).most_common(topK)]


if __name__ == '__main__':
    tests = [
        ('zh', 'Python是一种优雅的编程语言，支持面向对象编程'),
        ('ja', 'Pythonはエレガントなプログラミング言語です'),
        ('ko', 'Python은 우아한 프로그래밍 언어입니다'),
        ('he', 'Python היא שפת תכנות אלגנטית'),
        ('en', 'Python is an elegant programming language'),
    ]
    
    for lang, text in tests:
        detected = detect_lang(text)
        tok = tokenize(text)
        kw = extract_keywords(text, topK=5)
        status = '✅' if detected == lang else f'❌({detected})'
        print(f'{status} [{lang}] {tok[:70]}')
        print(f'  关键词: {kw}')
