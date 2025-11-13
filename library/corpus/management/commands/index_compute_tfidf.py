from django.core.management.base import BaseCommand
from corpus.models import Posting, Term, IndexStat
import math

class Command(BaseCommand):
    help = "计算 TF-IDF"

    def handle(self, *args, **opts):

        N_docs = int(IndexStat.objects.get(key="N_docs").value)

        # 一次性获取 df 映射：term_id → df
        terms_df = dict(Term.objects.values_list("id", "df"))

        total = Posting.objects.count()
        self.stdout.write(f"🔢 开始计算 TF-IDF，总 {total} 条记录...")

        batch = 50000
        qs = Posting.objects.all().order_by("id")

        for i in range(0, total, batch):
            chunk = list(qs[i : i + batch])

            for p in chunk:
                df = terms_df[p.term_id]
                idf = math.log((N_docs + 1) / (df + 1)) + 1
                p.tfidf = p.tf * idf

            Posting.objects.bulk_update(chunk, ["tfidf"])

            if i % 250000 == 0:
                self.stdout.write(f"  ... 已处理 {i} 条记录")

        self.stdout.write("✅ TF-IDF 计算完成")
