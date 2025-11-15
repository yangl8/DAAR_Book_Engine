import re
from django.db.models import Q
from corpus.models import Term, Posting, Book, DocumentScore
from nltk.stem import PorterStemmer
import time
from  .search_utils import preprocess_query, get_term_ids, compute_tfidf_for_books

from django.db.models import Q
from collections import defaultdict
from corpus.models import Term, Posting, Book, DocumentScore
from .search_utils import preprocess_query, get_term_ids, compute_tfidf_for_books


class SearchService:

    @staticmethod
    def search(query: str, centrality: str = "total", max_terms: int = 50, limit: int = 30):

        if not query:
            return []

        # clear & normalize query
        q_norm = query.strip().lower()
        if not q_norm:
            return []

        # 1) 分词（词干化）
        tokens = preprocess_query(query)
        if not tokens:
            return []

        # -------------------------------------------------------
        # 2) Multi-token TF-IDF
        #    每个 token 单独算 TF-IDF，然后归一化、最后合并
        # -------------------------------------------------------
        token_scores = []       # 每个 token 的 normalized TF-IDF 分布
        token_matches = []      # 每个 token 命中的 terms

        for tok in tokens:

            # --- 每个 token 单独查 term_ids ---
            term_ids_i = get_term_ids([tok])
            if not term_ids_i:
                continue

            # --- 每个 token 单独算 TF-IDF ---
            tfidf_i, matches_i = compute_tfidf_for_books(term_ids_i)
            if not tfidf_i:
                continue

            # --- normalize per token ---
            vals = list(tfidf_i.values())
            mi, ma = min(vals), max(vals)

            def norm_tf(v):
                if ma == mi:
                    return 0.0
                return (v - mi) / (ma - mi)

            normalized_map = {bid: norm_tf(v) for bid, v in tfidf_i.items()}

            token_scores.append(normalized_map)
            token_matches.append(matches_i)

        # 没有 token 匹配任何东西
        if not token_scores:
            return []

        # --- 合并所有 token 的 TF-IDF（已 normalize） ---
        tfidf_by_book = defaultdict(float)
        matched_terms = defaultdict(set)

        for score_map, match_map in zip(token_scores, token_matches):
            for bid, v in score_map.items():
                tfidf_by_book[bid] += v
                matched_terms[bid].update(match_map.get(bid, set()))

        if not tfidf_by_book:
            return []

        # -------------------------------------------------------
        # 3) book 信息 + centrality（沿用你的原逻辑）
        # -------------------------------------------------------
        book_ids = list(tfidf_by_book.keys())

        books = Book.objects.filter(text_id__in=book_ids)
        book_map = {b.text_id: b for b in books}

        scores = DocumentScore.objects.filter(book_id__in=book_ids)

        if centrality == "pagerank":
            cent_map = {s.book_id: s.pagerank for s in scores}
        elif centrality == "closeness":
            cent_map = {s.book_id: s.closeness for s in scores}
        elif centrality == "betweenness":
            cent_map = {s.book_id: s.betweenness for s in scores}
        elif centrality == "degree":
            cent_map = {s.book_id: s.popularity for s in scores}
        else:
            cent_map = {s.book_id: s.total for s in scores}

        # -------------------------------------------------------
        # 4) normalize centrality（仅中央性 normalize）
        # -------------------------------------------------------
        cents = [cent_map.get(bid, 0) for bid in book_ids]
        min_c, max_c = min(cents), max(cents)

        def norm_cent(v):
            if max_c == min_c:
                return 0.0
            return (v - min_c) / (max_c - min_c)

        # -------------------------------------------------------
        # 5) final score = a*tfidf + b*centrality
        # -------------------------------------------------------
        a = 0.7
        b = 0.3

        results = []

        for bid in book_ids:
            book = book_map[bid]

            tfidf_val = tfidf_by_book[bid]
            cent_val  = cent_map.get(bid, 0)
            cent_norm = norm_cent(cent_val)

            score = a * tfidf_val + b * cent_norm

            authors_raw = book.authors or ""
            authors_list = [x.strip() for x in authors_raw.split(",") if x.strip()]

            results.append({
                "book_id": book.text_id,
                "title": book.title,
                "authors": authors_list,
                "language": "en",
                "doc_len_tokens": book.doc_len_tokens,
                "snippet": "",
                "match_terms": sorted(matched_terms[bid]),
                "rank_features": {
                    "tfidf": tfidf_val,
                    "centrality": cent_val,
                    "score": score,
                },
                "score": score,
            })

        # 排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:limit]

# class SearchService:
#
#     @staticmethod
#     def search(query: str, centrality: str = "total", max_terms: int = 50, limit: int = 30):
#
#         if not query:
#             return []
#
#         # clear & normalize query
#         q_norm = query.strip().lower()
#         if not q_norm:
#             return []
#
#         tokens = preprocess_query(query)
#         if not tokens:
#             return []
#
#
#         # 2. find in table terms
#         term_ids = get_term_ids(tokens)
#         if not term_ids:
#             return []
#
#         # 3. find postings and TF-IDF
#         tfidf_by_book, matched_terms = compute_tfidf_for_books(term_ids)
#         if not tfidf_by_book:
#             return []
#
#         # 4. find info books and centrality
#
#         book_ids = list(tfidf_by_book.keys())
#
#         books = Book.objects.filter(text_id__in=book_ids)
#         book_map = {b.text_id: b for b in books}
#
#         scores = DocumentScore.objects.filter(book_id__in=book_ids)
#
#         if centrality == "pagerank":
#             cent_map = {s.book_id: s.pagerank for s in scores}
#         elif centrality == "closeness":
#             cent_map = {s.book_id: s.closeness for s in scores}
#         elif centrality == "betweenness":
#             cent_map = {s.book_id: s.betweenness for s in scores}
#         elif centrality == "degree":
#             cent_map = {s.book_id: s.popularity for s in scores}
#         else:
#             cent_map = {s.book_id: s.total for s in scores}
#
#
#         # 5. 多词命中加分
#
#         TERM_MATCH_BOOST = 1.5
#
#         raw_results = []
#
#         for bid in book_ids:
#             book = book_map.get(bid)
#             if not book:
#                 continue
#
#             tfidf_val = tfidf_by_book[bid]
#
#             # 命中多少 query 词
#             terms = matched_terms.get(bid, set())
#             num_matched = sum(1 for t in tokens if t in terms)
#
#             tfidf_val += num_matched * TERM_MATCH_BOOST
#
#             cent_val = cent_map.get(bid, 0)
#
#             raw_results.append((bid, book, tfidf_val, cent_val, terms, num_matched))
#
#
#         # 6. normalization tfidfs and cents
#
#         tfidfs = [x[2] for x in raw_results]
#         cents  = [x[3] for x in raw_results]
#
#         min_t, max_t = min(tfidfs), max(tfidfs)
#         min_c, max_c = min(cents), max(cents)
#
#         def norm(x, mi, ma):
#             if ma == mi:
#                 return 0.0
#             return (x - mi) / (ma - mi)
#
#         a = 0.7
#         b = 0.3
#
#         results = []
#
#         for bid, book, tfidf_val, cent_val, terms, num_matched in raw_results:
#
#             tfidf_norm = norm(tfidf_val, min_t, max_t)
#             cent_norm  = norm(cent_val, min_c, max_c)
#
#             score = a * tfidf_norm + b * cent_norm
#             authors_raw = book.authors or ""
#             authors_list = [a.strip() for a in authors_raw.split(",") if a.strip()]
#             results.append({
#                 "book_id": book.text_id,
#                 "title": book.title,
#                 "authors": authors_list,
#                 "language": "en",  # 你表里没有 language，就先固定写
#                 "doc_len_tokens": book.doc_len_tokens,
#                 "snippet": "",  # 之后再做 snippet
#                 "match_terms": sorted(terms),
#                 "rank_features": {
#                     "tfidf": tfidf_val,
#                     "centrality": cent_val,
#                     "score": score,  # 放一份进去给前端显示
#                 },
#                 "score": score,  # ⭐ 再放一份在顶层，给排序用
#             })
#
#         # 排序
#
#         results.sort(key=lambda x: x["score"], reverse=True)
#
#
#
#         return results[:limit]



    # 1) 按书名搜索
    @staticmethod
    def search_by_title(query: str, centrality: str = "total", limit: int = 20):
        """
        只在标题里搜，精确匹配/前缀匹配优先，然后再按中心性排序
        """
        if not query:
            return []

        q_norm = query.strip()
        if not q_norm:
            return []
        q_lower = q_norm.lower()

        # 1) 先找出标题里包含 query 的书
        books_qs = Book.objects.filter(title__icontains=q_norm)[:1000]  # 防止太多
        book_ids = [b.text_id for b in books_qs]
        if not book_ids:
            return []

        # 2) 拿中心性分数（total / pagerank / closeness / betweenness）
        scores_qs = DocumentScore.objects.filter(book_id__in=book_ids)
        cent_map = {}
        for s in scores_qs:
            if centrality == "pagerank":
                cent = s.pagerank or 0.0
            elif centrality == "closeness":
                cent = s.closeness or 0.0
            elif centrality == "betweenness":
                cent = s.betweenness or 0.0
            else:
                cent = s.total or 0.0
            cent_map[s.book_id] = cent

        results = []
        for b in books_qs:
            base_score = float(cent_map.get(b.text_id, 0.0))

            title = (b.title or "").strip()
            t_lower = title.lower()

            # 3) 根据标题匹配程度给 boost
            exact = (t_lower == q_lower)
            starts = t_lower.startswith(q_lower)
            contains = (q_lower in t_lower)

            boost = 0.0
            if exact:
                boost = 5.0     # 完全等于：大加分
            elif starts:
                boost = 2.0     # 以 query 开头：中等加分
            elif contains:
                boost = 0.5     # 只是在中间出现：小加分

            score = base_score + boost

            authors_raw = b.authors or ""
            authors_list = [x.strip() for x in authors_raw.split(",") if x.strip()]

            results.append({
                "book_id": b.text_id,
                "title": b.title,
                "authors": authors_list, # 你原来怎么填就怎么来
                "score": score,
            })

        # 4) 按最终 score 排序（从大到小）
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]
    
    # 2) 按作者搜索
    @staticmethod
    def search_by_author(query: str, centrality: str = "total", limit: int = 30):
        if not query:
            return []

        q_norm = query.strip()
        if not q_norm:
            return []

        tokens = [t for t in q_norm.split() if t]

        # 1. 在 Book 表里按作者模糊匹配
        qs = Book.objects.all()
        for tok in tokens:
            qs = qs.filter(authors__icontains=tok)

        books = list(qs[:200])
        if not books:
            return []

        book_ids = [b.text_id for b in books]

        # 2. 取 centrality
        scores = DocumentScore.objects.filter(book_id__in=book_ids)

        if centrality == "pagerank":
            cent_map = {s.book_id: s.pagerank for s in scores}
        elif centrality == "closeness":
            cent_map = {s.book_id: s.closeness for s in scores}
        elif centrality == "betweenness":
            cent_map = {s.book_id: s.betweenness for s in scores}
        elif centrality == "degree":
            cent_map = {s.book_id: s.popularity for s in scores}
        else:
            cent_map = {s.book_id: s.total for s in scores}

        results = []
        for b in books:
            authors_lower = (b.authors or "").lower()
            match_terms = [t for t in tokens if t.lower() in authors_lower]
            match_score = len(match_terms)

            cent_val = cent_map.get(b.text_id, 0.0)
            score = 0.7 * match_score + 0.3 * cent_val

            authors_raw = b.authors or ""
            authors_list = [x.strip() for x in authors_raw.split(",") if x.strip()]

            results.append({
                "book_id": b.text_id,
                "title": b.title,
                "authors": authors_list,
                "language": "en",
                "doc_len_tokens": b.doc_len_tokens,
                "snippet": "",
                "match_terms": match_terms,
                "rank_features": {
                    "author_match": match_score,
                    "centrality": cent_val,
                    "score": score,
                },
                "score": score,
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]