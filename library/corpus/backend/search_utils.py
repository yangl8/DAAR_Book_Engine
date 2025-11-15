
import re
from typing import List, Dict
from nltk.stem import PorterStemmer

from corpus.models import Term, Posting
# import spacy

# 1. query 前处理：lower + tokenize + stem
def preprocess_query(query: str):
    """
    把 SearchService 的 query 处理：lower → split → stem
    """
    if not query:
        return []

    q_norm = query.strip().lower()
    if not q_norm:
        return []

    # token 拆分
    tokens = [t for t in re.split(r"\W+", q_norm) if t]

    # 词干化（和 search 保持一致）
    stemmer = PorterStemmer()
    tokens = [stemmer.stem(t) for t in tokens]

    # 如果你之后改成 spaCy，这里统一替换即可：
    # nlp = spacy.load("en_core_web_sm")
    # tokens = [nlp(t)[0].lemma_.lower() for t in tokens]

    return tokens


# 2. term 匹配
# -----------------------------
def get_term_ids(tokens: List[str]) -> List[int]:
    """
    在 terms 表中查匹配的词项 id
    """
    if not tokens:
        return []
    qs = Term.objects.filter(term__in=tokens)
    return list(qs.values_list("id", flat=True))


# -----------------------------
# 3. posting 匹配 + 计算每本书的 TF-IDF
# -----------------------------
def compute_tfidf_for_books(term_ids: List[int]):
    """
    根据 term_ids 查 posting 表
    - 每本书的总 tfidf
    - 每本书中命中的 term 集合
    """
    if not term_ids:
        return {}, {}

    postings = Posting.objects.filter(term_id__in=term_ids).select_related("book", "term")

    tfidf_by_book = {}
    matched_terms = {}

    for p in postings:
        bid = p.book_id
        tfidf_by_book[bid] = tfidf_by_book.get(bid, 0.0) + p.tfidf
        matched_terms.setdefault(bid, set()).add(p.term.term)

    return tfidf_by_book, matched_terms
