from django.core.management.base import BaseCommand
from corpus.models import Book, Term, Posting, IndexStat
from collections import defaultdict
from pathlib import Path
import csv


class Command(BaseCommand):
    help = "导出 TF–IDF 与倒排索引测试数据（词典规模、posting 数、稀疏性等）"

    def handle(self, *args, **opts):

        # 输出文件路径
        out_global = Path("test/index_global_stats.csv")
        out_books  = Path("test/index_book_stats.csv")
        out_vocab  = Path("test/vocab_stats.csv")

        self.stdout.write("📊 导出 TF–IDF 与倒排索引统计数据...")

        # ===============================
        # 1. 全局统计
        # ===============================

        try:
            N_docs = int(IndexStat.objects.get(key="N_docs").value)
        except:
            N_docs = Book.objects.count()

        try:
            avg_doc_len = float(IndexStat.objects.get(key="avg_doc_len").value)
        except:
            if N_docs > 0:
                total_len = sum(Book.objects.values_list("doc_len_tokens", flat=True))
                avg_doc_len = total_len / N_docs
            else:
                avg_doc_len = 0

        vocab_size = Term.objects.count()
        posting_total = Posting.objects.count()

        # 写入 index_global_stats.csv
        with out_global.open("w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            w.writerow(["N_docs", N_docs])
            w.writerow(["avg_doc_len", avg_doc_len])
            w.writerow(["vocab_size_after_filter", vocab_size])
            w.writerow(["posting_total", posting_total])

        self.stdout.write(f"✅ 全局索引统计 → {out_global}")

        # ===============================
        # 2. 每本书的 TF–IDF 稀疏度等
        # ===============================
        with out_books.open("w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow([
                "book_id",
                "token_count",
                "tfidf_nonzero",
                "unique_terms",
                "sparsity_percent"
            ])

            for book in Book.objects.all():
                toks = book.doc_len_tokens
                postings = Posting.objects.filter(book=book)

                tfidf_nonzero = postings.count()
                unique_terms = len({p.term_id for p in postings})

                if vocab_size > 0:
                    sparsity = tfidf_nonzero / vocab_size * 100
                else:
                    sparsity = 0

                w.writerow([
                    book.text_id,
                    toks,
                    tfidf_nonzero,
                    unique_terms,
                    f"{sparsity:.3f}"
                ])

        self.stdout.write(f"✅ 每本书统计已写入 → {out_books}")

        # ===============================
        # 3. 词典统计（每个 term 的 df）
        # ===============================
        with out_vocab.open("w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow(["term_id", "term", "df"])

            for t in Term.objects.all():
                w.writerow([t.id, t.term, t.df])

        self.stdout.write(f"✅ 词典统计已写入 → {out_vocab}")

        self.stdout.write(self.style.SUCCESS("🎉 所有 CSV 文件生成完毕！"))
