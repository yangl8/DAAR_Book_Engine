# corpus/backend/recommendations.py

from typing import List, Dict
from django.db.models import Q
from corpus.models import Book, DocumentGraph, DocumentScore

from corpus.backend.search_utils import (
    preprocess_query,
    get_term_ids,
    compute_tfidf_for_books,
)


class RecommendationService:

    @staticmethod
    def recommend_for_query(query: str, limit: int = 6, seed_k: int = 3) -> List[Dict]:

        # -------------------------------------------------
        # 1. query 前处理
        # -------------------------------------------------
        tokens = preprocess_query(query)
        if not tokens:
            return []

        # -------------------------------------------------
        # 2. 查 term_ids
        # -------------------------------------------------
        term_ids = get_term_ids(tokens)
        if not term_ids:
            return []

        # -------------------------------------------------
        # 3. 查 posting + 计算 tfidf
        # -------------------------------------------------
        tfidf_by_book, _ = compute_tfidf_for_books(term_ids)
        if not tfidf_by_book:
            return []

        # -------------------------------------------------
        # 4. 按 tfidf 排序，选 top seed_k 作为推荐种子
        # -------------------------------------------------
        sorted_books = sorted(tfidf_by_book.items(), key=lambda x: x[1], reverse=True)
        seed_ids = [bid for bid, _ in sorted_books[:seed_k]]

        if not seed_ids:
            return []

        # -------------------------------------------------
        # 5. 从 G_d (DocumentGraph) 找邻居（cosine similarity）
        # -------------------------------------------------
        edges = DocumentGraph.objects.filter(
            Q(doc1_id__in=seed_ids) | Q(doc2_id__in=seed_ids)
        )

        neighbor_scores = {}

        for edge in edges:
            if edge.doc1_id in seed_ids:
                nid = edge.doc2_id
            else:
                nid = edge.doc1_id

            if nid in seed_ids:
                continue

            sim = edge.similarity
            if nid not in neighbor_scores or sim > neighbor_scores[nid]:
                neighbor_scores[nid] = sim

        if not neighbor_scores:
            return []

        neighbor_ids = list(neighbor_scores.keys())

        # -------------------------------------------------
        # 6. 拉取书籍信息 + centrality
        # -------------------------------------------------
        books = Book.objects.filter(text_id__in=neighbor_ids)
        scores = DocumentScore.objects.filter(book_id__in=neighbor_ids)
        score_map = {s.book_id: s for s in scores}

        results = []

        for b in books:
            s = score_map.get(b.text_id)
            results.append({
                "book_id": b.text_id,
                "title": b.title,
                "authors": b.authors,
                "similarity": neighbor_scores[b.text_id],  # cosine
                "total": s.total if s else None,
                "pagerank": s.pagerank if s else None,
            })

        # -------------------------------------------------
        # 7. 按 similarity + total 排序
        # -------------------------------------------------
        results.sort(
            key=lambda r: (-r["similarity"], -(r["total"] or 0))
        )

        return results[:limit]
