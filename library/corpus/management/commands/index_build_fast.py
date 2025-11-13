from django.core.management.base import BaseCommand
from django.db import transaction, models, connection
from pathlib import Path
import csv, re
from collections import Counter

from corpus.models import Book, Term, Posting, IndexStat

# ========= 文本清洗 =========
START_RE = re.compile(r'\*{3}\s*START OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
END_RE   = re.compile(r'\*{3}\s*END OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
LICENSE_RE = re.compile(r'START:\s*FULL\s*LICENSE', re.I)
WORD_RE = re.compile(r"[A-Za-z0-9']+")

# ========= 停用词 =========
STOPWORDS = {
    'a','an','and','are','as','at','be','but','by','for','if','in','into','is','it',
    'no','not','of','on','or','such','that','the','their','then','there','these',
    'they','this','to','was','will','with','so','than','too','very','can','from',
    'do','does','did','am','have','has','had',
    'he','him','his','she','her','hers','me','my','mine','you','your','yours',
    'we','our','ours','us','them','those','which','what','who','whom',
    'been','being','shall','should','would','could','may','might','must',
    'i','im','youre','youve','youll','cant','dont','didnt','wont','theres',
    'here','there','where','when','why','how','any','all','each','every','few',
    'more','most','other','some','only','own','same','so','too',
    's','t','just','now','o','u','one','two','three','four','five'
}

# ========= 词干提取（满足老师要求） =========
from nltk.stem import PorterStemmer
stemmer = PorterStemmer()

# ========= 清洗文本 =========
def clean_text(raw):
    m1 = LICENSE_RE.search(raw)
    cut = raw[:m1.start()] if m1 else raw
    m2 = START_RE.search(cut)
    body = cut[m2.end():] if m2 else cut
    m3 = END_RE.search(body)
    return body[:m3.start()] if m3 else body

# ========= tokenize：清洗 + 去引号 + 词干 =========
def tokenize(s):
    tokens = []
    for tok in WORD_RE.findall(s):
        tok = tok.lower()

        tok = tok.strip("'")
        if tok.endswith("'s"):
            tok = tok[:-2]
        elif tok.endswith("'"):
            tok = tok[:-1]

        if len(tok) < 2:
            continue
        if tok in STOPWORDS:
            continue
        if tok.isdigit():
            continue

        tok = stemmer.stem(tok)
        if len(tok) < 2:
            continue

        tokens.append(tok)

    return tokens


# ========= 主命令 =========
class Command(BaseCommand):
    help = "构建倒排索引（词干 + TopK + DF过滤 + cascade delete）"

    def add_arguments(self, parser):
        parser.add_argument("--meta", default="../selected_meta.csv")
        parser.add_argument("--dir", default="../books_html_kept")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--topk", type=int, default=3000)
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args, **opts):

        meta_csv = Path(opts["meta"]).resolve()
        book_dir = Path(opts["dir"]).resolve()

        rows = list(csv.DictReader(meta_csv.open(encoding="utf8", errors="ignore")))
        if opts["limit"] > 0:
            rows = rows[:opts["limit"]]

        topk = opts["topk"]
        bsize = opts["batch_size"]

        posting_buf = []
        term_cache = {}
        df_counter = {}

        def flush():
            nonlocal posting_buf
            if posting_buf:
                Posting.objects.bulk_create(posting_buf, batch_size=bsize)
                posting_buf = []

        total_docs = 0
        total_len  = 0

        self.stdout.write("🚀 开始构建倒排索引（词干化）...")

        with transaction.atomic():

            # ====== 遍历每本书 ======
            for i, row in enumerate(rows, 1):

                tid = (row.get("Text#") or "").strip()
                if not tid.isdigit(): continue
                tid = int(tid)

                p = book_dir / f"{tid}.txt"
                if not p.exists(): continue

                raw = p.read_text(encoding="utf8", errors="ignore")
                toks = tokenize(clean_text(raw))
                if not toks: continue

                rel_path = f"books_html_kept/{tid}.txt"

                book, _ = Book.objects.update_or_create(
                    text_id=tid,
                    defaults=dict(
                        title=row.get("Title",""),
                        authors=row.get("Authors",""),
                        local_path=rel_path,
                        doc_len_tokens=len(toks),
                    )
                )

                total_docs += 1
                total_len  += len(toks)

                counter = Counter(toks)

                # ====== TopK 高频 ======
                for term_str, tf in counter.most_common(topk):

                    if term_str not in term_cache:
                        t, _ = Term.objects.get_or_create(term=term_str, defaults={"df":0})
                        term_cache[term_str] = t.id
                        df_counter.setdefault(term_str, 0)

                    posting_buf.append(Posting(
                        term_id=term_cache[term_str],
                        book=book,
                        tf=tf
                    ))

                    if len(posting_buf) >= bsize:
                        flush()

                # DF++
                for t in counter.keys():
                    df_counter[t] = df_counter.get(t, 0) + 1

                if i % 50 == 0:
                    self.stdout.write(f"  … 已处理 {i} 本书")

            flush()

            # ====== 写回 DF ======
            for t, df in df_counter.items():
                Term.objects.filter(term=t).update(df=models.F("df") + df)

            avg = total_len / total_docs
            IndexStat.objects.update_or_create(key="N_docs", defaults={"value": str(total_docs)})
            IndexStat.objects.update_or_create(key="avg_doc_len", defaults={"value": str(avg)})

            N = total_docs

            # ===== 高频词清理 95% =====
            Term.objects.filter(df__gte=int(N * 0.95)).delete()

            # ===== 中频词清理 40% =====
            Term.objects.filter(df__gte=int(N * 0.40)).delete()

            # ===== 低频词清理 =====
            Term.objects.filter(df__lte=2).delete()

            # ===== 清理孤立 postings =====
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM postings
                    WHERE term_id NOT IN (SELECT id FROM terms)
                """)

            # ===== 重新计算 DF =====
            for term in Term.objects.all():
                df = Posting.objects.filter(term_id=term.id).values('book_id').distinct().count()
                term.df = df
                term.save()

        self.stdout.write(self.style.SUCCESS("🎉 倒排索引构建完成（词干 + 三层过滤 + 级联删除）"))
