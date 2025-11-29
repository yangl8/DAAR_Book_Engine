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

        # 1) Tokenisation (stemming)
        tokens = preprocess_query(query)
        if not tokens:
            return []

        # -------------------------------------------------------
        # 2) Multi-token TF-IDF
        #    Calculer le TF-IDF pour chaque token, normaliser puis fusionner
        # -------------------------------------------------------
        token_scores = []       # Distribution TF-IDF normalisée pour chaque token
        token_matches = []      # Termes correspondants pour chaque token

        for tok in tokens:

            # --- Rechercher les term_ids pour chaque token ---
            term_ids_i = get_term_ids([tok])
            if not term_ids_i:
                continue

            # --- Calculer le TF-IDF pour chaque token ---
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

        # Aucun token n'a donné de correspondance
        if not token_scores:
            return []

        # --- Fusionner tous les TF-IDF par token (déjà normalisés) ---
        tfidf_by_book = defaultdict(float)
        matched_terms = defaultdict(set)

        for score_map, match_map in zip(token_scores, token_matches):
            for bid, v in score_map.items():
                tfidf_by_book[bid] += v
                matched_terms[bid].update(match_map.get(bid, set()))

        if not tfidf_by_book:
            return []

        # -------------------------------------------------------
        # 3) Informations sur les livres + centralité (logique existante)
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
        # 4) Normaliser la centralité (ne normaliser que la centralité)
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

        # Tri
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
#         # 5. Bonus pour les correspondances multi-termes
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
#             # Compter combien de termes de la requête sont présents
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
#                 "language": "en",  # Pas de champ language dans ta table, on fixe donc à "en"
#                 "doc_len_tokens": book.doc_len_tokens,
#                 "snippet": "",  # Snippet à ajouter ultérieurement
#                 "match_terms": sorted(terms),
#                 "rank_features": {
#                     "tfidf": tfidf_val,
#                     "centrality": cent_val,
#                     "score": score,  # Garder une copie pour l'affichage front
#                 },
#                 "score": score,  # Conserver aussi au niveau supérieur pour le tri
#             })
#
#         # Tri
#
#         results.sort(key=lambda x: x["score"], reverse=True)
#
#
#
#         return results[:limit]



    # 1) Recherche par titre
    @staticmethod
    def search_by_title(query: str, centrality: str = "total", limit: int = 20):
        """
        Rechercher uniquement dans le titre, privilégier les correspondances exactes/préfixes puis trier par centralité
        """
        if not query:
            return []

        q_norm = query.strip()
        if not q_norm:
            return []
        q_lower = q_norm.lower()

        # 1) Rechercher les livres dont le titre contient la requête
        books_qs = Book.objects.filter(title__icontains=q_norm)[:1000]  # Limiter le volume
        book_ids = [b.text_id for b in books_qs]
        if not book_ids:
            return []

        # 2) Récupérer les scores de centralité (total / pagerank / closeness / betweenness)
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

        # 3) Appliquer un bonus selon la qualité de correspondance du titre
            exact = (t_lower == q_lower)
            starts = t_lower.startswith(q_lower)
            contains = (q_lower in t_lower)

            boost = 0.0
            if exact:
                boost = 5.0     # Égalité exacte : fort bonus
            elif starts:
                boost = 2.0     # Le titre commence par la requête : bonus moyen
            elif contains:
                boost = 0.5     # La requête apparaît au milieu : petit bonus

            score = base_score + boost

            authors_raw = b.authors or ""
            authors_list = [x.strip() for x in authors_raw.split(",") if x.strip()]

            results.append({
                "book_id": b.text_id,
                "title": b.title,
                "authors": authors_list, # Conserver le même remplissage qu'auparavant
                "score": score,
            })

        # 4) Trier par score final (ordre décroissant)
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]
    
    # 2) Recherche par auteur
    @staticmethod
    def search_by_author(query: str, centrality: str = "total", limit: int = 30):
        if not query:
            return []

        q_norm = query.strip()
        if not q_norm:
            return []

        tokens = [t for t in q_norm.split() if t]

        # 1. Effectuer une recherche floue sur les auteurs dans la table Book
        qs = Book.objects.all()
        for tok in tokens:
            qs = qs.filter(authors__icontains=tok)

        books = list(qs[:200])
        if not books:
            return []

        book_ids = [b.text_id for b in books]

        # 2. Récupérer la centralité
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