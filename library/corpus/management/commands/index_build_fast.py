from django.core.management.base import BaseCommand
from django.db import transaction, models
from pathlib import Path
import csv, re
from collections import Counter

from corpus.models import Book, Term, Posting, IndexStat

START_RE   = re.compile(r'\*{3}\s*START OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
END_RE     = re.compile(r'\*{3}\s*END OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
LICENSE_RE = re.compile(r'START:\s*FULL\s*LICENSE', re.I)
WORD_RE    = re.compile(r"[A-Za-z0-9']+")

STOPWORDS = {
    'a','an','and','are','as','at','be','but','by','for','if','in','into','is','it',
    'no','not','of','on','or','such','that','the','their','then','there','these',
    'they','this','to','was','will','with','so','than','too','very','can','from'
}

def clean_text(raw):
    m1 = LICENSE_RE.search(raw)
    cut = raw[:m1.start()] if m1 else raw
    m2 = START_RE.search(cut)
    body = cut[m2.end():] if m2 else cut
    m3 = END_RE.search(body)
    return body[:m3.start()] if m3 else body

def tokenize(s):
    toks = (t.lower() for t in WORD_RE.findall(s))
    return [t for t in toks if len(t)>=2 and t not in STOPWORDS and not t.isdigit()]


class Command(BaseCommand):
    help = "高速构建倒排索引（TopK + bulk_create）"

    def add_arguments(self, parser):
        parser.add_argument("--meta", default="../selected_meta.csv")
        parser.add_argument("--dir", default="../books_html_kept")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--topk", type=int, default=3000)
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args, **opts):

        meta_csv = Path(opts["meta"]).resolve()
        book_dir = Path(opts["dir"]).resolve()

        with meta_csv.open(newline="", encoding="utf8", errors="ignore") as f:
            rows = list(csv.DictReader(f))

        if opts["limit"] > 0:
            rows = rows[:opts["limit"]]

        topk = opts["topk"]
        bsize = opts["batch_size"]

        posting_buf = []
        term_cache  = {}    # term → Term.id
        df_counter  = {}    # term → df-increment

        def flush():
            nonlocal posting_buf
            if posting_buf:
                Posting.objects.bulk_create(posting_buf, batch_size=bsize)
                posting_buf = []

        total_docs = 0
        total_len  = 0

        self.stdout.write("🚀 开始构建倒排索引…")

        with transaction.atomic():

            for i, row in enumerate(rows, 1):

                tid = (row.get("Text#") or "").strip()
                if not tid.isdigit():
                    continue
                tid = int(tid)

                txt = book_dir / f"{tid}.txt"
                if not txt.exists():
                    continue

                raw = txt.read_text(encoding="utf8", errors="ignore")
                toks = tokenize(clean_text(raw))
                if not toks:
                    continue

                rel_path = f"books_html_kept/{tid}.txt"

                book, _ = Book.objects.update_or_create(
                    text_id=tid,
                    defaults=dict(
                        title=row.get("Title", ""),
                        authors=row.get("Authors", ""),
                        local_path=rel_path,
                        doc_len_tokens=len(toks),
                    )
                )

                total_docs += 1
                total_len  += len(toks)

                counter = Counter(toks)

                for term_str, tf in counter.most_common(topk):

                    if term_str not in term_cache:
                        term_obj, _ = Term.objects.get_or_create(term=term_str, defaults={"df":0})
                        term_cache[term_str] = term_obj.id
                        df_counter.setdefault(term_str, 0)

                    posting_buf.append(Posting(
                        term_id=term_cache[term_str],
                        book=book,
                        tf=tf
                    ))

                    if len(posting_buf) >= bsize:
                        flush()

                for t in counter:
                    df_counter[t] = df_counter.get(t, 0) + 1

                if i % 50 == 0:
                    self.stdout.write(f"  … 已处理 {i} 本书")

            flush()

            # 正确累加 DF（不能覆盖）
            for t, df in df_counter.items():
                Term.objects.filter(term=t).update(df=models.F("df") + df)

            avg = total_len / total_docs
            IndexStat.objects.update_or_create(key="N_docs",      defaults={"value": str(total_docs)})
            IndexStat.objects.update_or_create(key="avg_doc_len", defaults={"value": str(avg)})

        self.stdout.write(self.style.SUCCESS(f"✅ 完成：{total_docs} 本书，平均长度={avg:.2f}"))
