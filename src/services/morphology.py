from __future__ import annotations

import re
from functools import lru_cache

from nltk.stem.snowball import SnowballStemmer

_WORD_PATTERN = re.compile(r"[0-9a-zа-яё]+")
_CYRILLIC_PATTERN = re.compile(r"[а-яё]")
_LATIN_PATTERN = re.compile(r"[a-z]")


@lru_cache(maxsize=2)
def _get_stemmer(language: str) -> SnowballStemmer:
    return SnowballStemmer(language)


def tokenize(text: str) -> list[str]:
    """Разбить текст на слова: буквы и цифры, регистр и «ё» не учитываются."""
    return _WORD_PATTERN.findall(text.casefold().replace("ё", "е"))


@lru_cache(maxsize=10_000)
def stem(word: str) -> str:
    """Вернуть основу слова (русского или английского); числа остаются как есть."""
    word = word.casefold().replace("ё", "е")
    if _CYRILLIC_PATTERN.search(word):
        return _get_stemmer("russian").stem(word)
    if _LATIN_PATTERN.search(word):
        return _get_stemmer("english").stem(word)
    return word


def text_matches_query(text: str, query: str) -> bool:
    """Проверить, что каждое слово запроса (с учётом морфологии) встречается в тексте."""
    query_stems = [stem(token) for token in tokenize(query)]
    if not query_stems:
        return True
    text_stems = [stem(token) for token in tokenize(text)]
    return all(any(t.startswith(q) for t in text_stems) for q in query_stems)
