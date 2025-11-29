from django.core.management.base import BaseCommand
from corpus.models import Book, Posting, DocumentGraph
from math import sqrt

class Command(BaseCommand):
    help = "Build document similarity graph (G_d) using cosine similarity."

    # ----------------------------
    # Calculer le cosinus de deux vecteurs TF-IDF
    # ----------------------------
    def cosine(self, vecA, vecB):
        # Seuls les termes communs contribuent au produit scalaire
        common_terms = set(vecA.keys()) & set(vecB.keys())

        if not common_terms:
            return 0.0

        dot = sum(vecA[t] * vecB[t] for t in common_terms)

        normA = sqrt(sum(v*v for v in vecA.values()))
        normB = sqrt(sum(v*v for v in vecB.values()))

        if normA == 0 or normB == 0:
            return 0.0

        return dot / (normA * normB)

    # ----------------------------
    # Logique principale : construire G_d
    # ----------------------------
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Building document graph (G_d)..."))

        DocumentGraph.objects.all().delete()
        self.stdout.write("Cleared old document_graph table.")

        # Récupérer tous les livres
        books = list(Book.objects.all())
        total = len(books)

        # Précharger les vecteurs
        vectors = {}

        for book in books:
            postings = Posting.objects.filter(book=book, tfidf__gt=0)
            vectors[book.text_id] = {p.term_id: p.tfidf for p in postings}

        # Considérer deux livres comme similaires si la similarité dépasse 0,05
        threshold = 0.05

        # Calculer toutes les paires
        for i in range(total):
            for j in range(i+1, total):
                idA = books[i].text_id
                idB = books[j].text_id

                sim = self.cosine(vectors[idA], vectors[idB])

                if sim >= threshold:
                    DocumentGraph.objects.create(
                        doc1_id=idA,
                        doc2_id=idB,
                        similarity=sim
                    )
                    self.stdout.write(
                        f"Edge: {idA} <-> {idB}, sim={sim:.4f}"
                    )

        self.stdout.write(self.style.SUCCESS("Document graph G_d built successfully!"))
