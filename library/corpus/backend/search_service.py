import re
from django.db.models import Q
from corpus.models import Term, Posting, Book, DocumentScore
from nltk.stem import PorterStemmer
import spacy
import time

class SearchService:

    @staticmethod
    def search(query: str, centrality: str = "total", max_terms: int = 50, limit: int = 30):

        start = time.time()
        if not query:
            return []

        # clear & normalize query
        q_norm = query.strip().lower()
        if not q_norm:
            return []

        #annalay token
        tokens = [t for t in re.split(r"\W+", q_norm) if t]
        #傻子
        stemmer = PorterStemmer()
        tokens = [stemmer.stem(t) for t in tokens]
        #聪明的
        # nlp = spacy.load("en_core_web_sm")
        # tokens = [nlp(t)[0].lemma_.lower() for t in tokens]
        if not tokens:
            return []


        # 2. find in table terms
        term_qs = Term.objects.filter(term__in=tokens)[:max_terms]
        term_ids = list(term_qs.values_list("id", flat=True))


        # 3. find postings and TF-IDF

        postings = (
            Posting.objects
            .filter(term_id__in=term_ids)
            .select_related("book", "term")
        )

        tfidf_by_book = {}
        matched_terms = {}

        for p in postings:
            bid = p.book_id
            tfidf_by_book[bid] = tfidf_by_book.get(bid, 0.0) + p.tfidf

            if bid not in matched_terms:
                matched_terms[bid] = set()
            matched_terms[bid].add(p.term.term)

        # 没结果
        if not tfidf_by_book:
            return []


        # 4. find info books and centrality

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


        # 5. 多词命中加分

        TERM_MATCH_BOOST = 1.5

        raw_results = []

        for bid in book_ids:
            book = book_map.get(bid)
            if not book:
                continue

            tfidf_val = tfidf_by_book[bid]

            # 命中多少 query 词
            terms = matched_terms.get(bid, set())
            num_matched = sum(1 for t in tokens if t in terms)

            tfidf_val += num_matched * TERM_MATCH_BOOST

            cent_val = cent_map.get(bid, 0)

            raw_results.append((bid, book, tfidf_val, cent_val, terms, num_matched))


        # 6. normalization tfidfs and cents

        tfidfs = [x[2] for x in raw_results]
        cents  = [x[3] for x in raw_results]

        min_t, max_t = min(tfidfs), max(tfidfs)
        min_c, max_c = min(cents), max(cents)

        def norm(x, mi, ma):
            if ma == mi:
                return 0.0
            return (x - mi) / (ma - mi)

        a = 0.7
        b = 0.3

        results = []

        for bid, book, tfidf_val, cent_val, terms, num_matched in raw_results:

            tfidf_norm = norm(tfidf_val, min_t, max_t)
            cent_norm  = norm(cent_val, min_c, max_c)

            score = a * tfidf_norm + b * cent_norm
            authors_raw = book.authors or ""
            authors_list = [a.strip() for a in authors_raw.split(",") if a.strip()]
            results.append({
                "book_id": book.text_id,
                "title": book.title,
                "authors": authors_list,
                "language": "en",  # 你表里没有 language，就先固定写
                "doc_len_tokens": book.doc_len_tokens,
                "snippet": "",  # 之后再做 snippet
                "match_terms": sorted(terms),
                "rank_features": {
                    "tfidf": tfidf_val,
                    "centrality": cent_val,
                    "score": score,  # 放一份进去给前端显示
                },
                "score": score,  # ⭐ 再放一份在顶层，给排序用
            })

        # 排序

        results.sort(key=lambda x: x["score"], reverse=True)

        elapsed = (time.time() - start) * 1000

        return results[:limit]

# # add score for author and title
#
# class SearchService:
#
#     @staticmethod
#     def search(query: str, centrality: str = "total", max_terms: int = 50, limit: int = 30):
#
#         if not query:
#             return []
#
#         # Normalize query
#         q_norm = query.strip().lower()
#         if not q_norm:
#             return []
#
#         # ------------------------------
#         # 1. Tokenize query
#         # ------------------------------
#         tokens = [t for t in re.split(r"\W+", q_norm) if t]
#         if not tokens:
#             return []
#
#         # ------------------------------
#         # 2. Exact match terms (fix icontains issue)
#         # ------------------------------
#         term_qs = Term.objects.filter(term__in=tokens)[:max_terms]
#         term_ids = list(term_qs.values_list("id", flat=True))
#
#         # ------------------------------
#         # 3. Postings → accumulate TF-IDF
#         # ------------------------------
#         postings = (
#             Posting.objects
#             .filter(term_id__in=term_ids)
#             .select_related("book", "term")
#         )
#
#         tfidf_by_book = {}
#         matched_terms = {}
#
#         for p in postings:
#             bid = p.book_id
#             tfidf_by_book[bid] = tfidf_by_book.get(bid, 0.0) + p.tfidf
#
#             if bid not in matched_terms:
#                 matched_terms[bid] = set()
#             matched_terms[bid].add(p.term.term)
#
#         # ------------------------------
#         # 4. Title / author hit (using q_norm or tokens)
#         # ------------------------------
#         TITLE_BOOST = 5.0
#         AUTHOR_BOOST = 3.0
#
#         title_filter = Q()
#         author_filter = Q()
#
#         for t in tokens:
#             title_filter |= Q(title__icontains=t)
#             author_filter |= Q(authors__icontains=t)
#
#         title_hit = set(Book.objects.filter(title_filter).values_list("text_id", flat=True))
#         author_hit = set(Book.objects.filter(author_filter).values_list("text_id", flat=True))
#
#         # Add boosts
#         for bid in title_hit:
#             tfidf_by_book[bid] = tfidf_by_book.get(bid, 0.0) + TITLE_BOOST
#         for bid in author_hit:
#             tfidf_by_book[bid] = tfidf_by_book.get(bid, 0.0) + AUTHOR_BOOST
#
#         if not tfidf_by_book:
#             return []
#
#         # ------------------------------
#         # 5. Fetch books + centrality
#         # ------------------------------
#         book_ids = list(tfidf_by_book.keys())
#         books = Book.objects.filter(text_id__in=book_ids)
#         book_map = {b.text_id: b for b in books}
#
#         scores = DocumentScore.objects.filter(book_id__in=book_ids)
#
#         # Select centrality field dynamically
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
#         # ------------------------------
#         # 6. Multi-term match boost
#         # ------------------------------
#         TERM_MATCH_BOOST = 1.5
#
#         results_raw = []
#
#         for bid in book_ids:
#             book = book_map.get(bid)
#             if not book:
#                 continue
#
#             tfidf_val = tfidf_by_book[bid]
#
#             # count matched query words
#             terms = matched_terms.get(bid, set())
#             num_match = sum(1 for t in tokens if t in terms)
#
#             tfidf_val += num_match * TERM_MATCH_BOOST
#
#             cent_val = cent_map.get(bid, 0)
#             results_raw.append((bid, book, tfidf_val, cent_val, terms, num_match))
#
#         # ------------------------------
#         # 7. NORMALIZATION (make 70%/30% real)
#         # ------------------------------
#         tfidfs = [x[2] for x in results_raw]
#         cents = [x[3] for x in results_raw]
#
#         min_t, max_t = min(tfidfs), max(tfidfs)
#         min_c, max_c = min(cents), max(cents)
#
#         def norm(val, minv, maxv):
#             if maxv == minv:
#                 return 0.0
#             return (val - minv) / (maxv - minv)
#
#         a = 0.7
#         b = 0.3
#
#         results = []
#
#         for bid, book, tfidf_val, cent_val, terms, num_match in results_raw:
#             tfidf_norm = norm(tfidf_val, min_t, max_t)
#             cent_norm = norm(cent_val, min_c, max_c)
#
#             score = a * tfidf_norm + b * cent_norm
#
#             results.append({
#                 "book_id": book.text_id,
#                 "title": book.title,
#                 "authors": book.authors,
#                 "tfidf": tfidf_val,
#                 "centrality_total": cent_val,
#                 "score": score,
#                 "matched_terms": sorted(terms),
#                 "matched_token_count": num_match,
#                 "title_hit": bid in title_hit,
#                 "author_hit": bid in author_hit,
#             })
#
#         results.sort(key=lambda x: x["score"], reverse=True)
#
#         return results[:limit]
