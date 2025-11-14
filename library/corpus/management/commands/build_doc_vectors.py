from django.core.management.base import BaseCommand
from corpus.models import Posting, Book

class Command(BaseCommand):
    help = "Build TF-IDF vectors for all documents (in memory only)."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Building TF-IDF vectors..."))

        # 1️⃣ 获取全部书籍
        all_books = Book.objects.all()
        self.stdout.write(f"Total books = {all_books.count()}")

        # 2️⃣ 遍历每本书
        for book in all_books:
            # 查所有 (term_id, tfidf)
            postings = Posting.objects.filter(book=book, tfidf__gt=0)

            # 3️⃣ 构建稀疏向量：term_id → tfidf
            vector = {p.term_id: p.tfidf for p in postings}

            # 显示一个示例
            self.stdout.write(
                f"Book {book.text_id}: vector size = {len(vector)}"
            )

        self.stdout.write(self.style.SUCCESS("TF-IDF vectors built successfully!"))
