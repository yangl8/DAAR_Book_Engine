from django.core.management.base import BaseCommand
from django.db import transaction, connection
from pathlib import Path
import csv, re
from collections import Counter

from corpus.models import Book, Term, Posting, IndexStat

# ========= 文本清洗 =========
START_RE = re.compile(r'\*{3}\s*START OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
END_RE   = re.compile(r'\*{3}\s*END OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
LICENSE_RE = re.compile(r"START:\s*FULL\s*LICENSE", re.I)

# ========= 词抽取：只允许 a-z =========
WORD_RE = re.compile(r"[A-Za-z]+")

# ========= 停用词 =========
STOPWORDS = {
    "a","an","and","are","as","at","be","but","by","for","if","in","into","is","it",
    "no","not","of","on","or","such","that","the","their","then","there","these",
    "they","this","to","was","will","with","so","than","too","very","can","from",
    "do","does","did","am","have","has","had",
    "he","him","his","she","her","hers","me","my","mine","you","your","yours",
    "we","our","ours","us","them","those","which","what","who","whom",
    "been","being","shall","should","would","could","may","might","must",
    "i","im","youre","youve","youll","cant","dont","didnt","wont","theres",
    "here","where","when","why","how","any","all","each","every","few",
    "more","most","other","some","only","own","same","too",
}

# ========= 词干提取（PorterStemmer）=========
from nltk.stem import PorterStemmer
stemmer = PorterStemmer()


# ========= 清洗文本：去掉 License、开头、结尾 =========
def clean_text(raw: str) -> str:
    # 先切掉 LICENSE
    m1 = LICENSE_RE.search(raw)
    cut = raw[:m1.start()] if m1 else raw

    # 再切掉 "*** START OF ..."
    m2 = START_RE.search(cut)
    body = cut[m2.end():] if m2 else cut

    # 最后切掉 "*** END OF ..."
    m3 = END_RE.search(body)
    body = body[:m3.start()] if m3 else body

    return body


# ========= tokenize：分词 + 小写 + 停用词 + 长度过滤 + 词干 =========
def tokenize(s: str):
    tokens = []
    for tok in WORD_RE.findall(s):
        tok = tok.lower()

        if tok in STOPWORDS:
            continue
        if len(tok) < 2:
            continue
        # 可选：过滤特别长的 token，很多是噪声
        if len(tok) > 25:
            continue

        tok = stemmer.stem(tok)
        tokens.append(tok)

    return tokens


# ========= 主命令 =========
class Command(BaseCommand):
    help = "构建倒排索引（正确 DF 顺序，TopK + 高频/低频过滤）"

    def add_arguments(self, parser):
        parser.add_argument("--meta", default="../selected_meta.csv")
        parser.add_argument("--dir", default="../books_html_kept")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--topk", type=int, default=3000)      # 每本书最多取 topK 词
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args, **opts):

        meta_csv = Path(opts["meta"]).resolve()
        book_dir = Path(opts["dir"]).resolve()
        rows = list(csv.DictReader(meta_csv.open(encoding="utf8", errors="ignore")))

        if opts["limit"] > 0:
            rows = rows[:opts["limit"]]

        topk  = opts["topk"]
        bsize = opts["batch_size"]

        posting_buf = []
        term_cache = {}   # term_str -> term_id

        total_docs = 0
        total_len  = 0

        self.stdout.write("🚀 开始构建倒排索引...")

        with transaction.atomic():

            # ===== 0. 清空旧数据（只在单独索引库中这么干）=====
            Posting.objects.all().delete()
            Term.objects.all().delete()

            # ===== 1. 遍历书籍：清洗 + tokenize + Counter + TopK + 写 Posting =====
            for i, row in enumerate(rows, 1):

                tid_str = (row.get("Text#") or "").strip()
                if not tid_str.isdigit():
                    continue
                tid = int(tid_str)

                p = book_dir / f"{tid}.txt"
                if not p.exists():
                    continue

                raw = p.read_text(encoding="utf8", errors="ignore")
                toks = tokenize(clean_text(raw))

                if not toks:
                    continue

                book, _ = Book.objects.update_or_create(
                    text_id=tid,
                    defaults=dict(
                        title=row.get("Title", ""),
                        authors=row.get("Authors", ""),
                        local_path=f"books_html_kept/{tid}.txt",
                        doc_len_tokens=len(toks),
                    )
                )

                total_docs += 1
                total_len  += len(toks)

                counter = Counter(toks)

                # TopK 高频词（topk <=0 表示不用截断）
                if topk and topk > 0:
                    items = counter.most_common(topk)
                else:
                    items = counter.items()

                for term_str, tf in items:
                    if term_str not in term_cache:
                        t = Term.objects.create(term=term_str, df=0)
                        term_cache[term_str] = t.id

                    posting_buf.append(Posting(
                        term_id=term_cache[term_str],
                        book=book,
                        tf=tf,
                    ))

                    if len(posting_buf) >= bsize:
                        Posting.objects.bulk_create(posting_buf, batch_size=bsize)
                        posting_buf = []

                if i % 50 == 0:
                    self.stdout.write(f"… 已处理 {i} 本书")

            if posting_buf:
                Posting.objects.bulk_create(posting_buf, batch_size=bsize)

            if total_docs == 0:
                self.stdout.write(self.style.WARNING("⚠ 没有成功处理任何书，结束。"))
                return

            # ===== 2. 正确计算 DF（唯一来源 = Posting）=====
            self.stdout.write("🔍 重新计算 DF ...")
            for term in Term.objects.all():
                df = (
                    Posting.objects
                    .filter(term_id=term.id)
                    .values("book_id")
                    .distinct()
                    .count()
                )
                term.df = df
                term.save()

            N = total_docs

            # ===== 3. DF 过滤：高频 + 低频 =====
            self.stdout.write("🧹 按 DF 做高频 / 低频 清理 ...")

            # 高频：DF >= 95% 文档（the, and, of...）
            high_cut = int(N * 0.95)
            if high_cut > 0:
                Term.objects.filter(df__gte=high_cut).delete()

            # 低频：DF <= 2（噪声、拼写错误、人名等）
            Term.objects.filter(df__lte=2).delete()

            # ===== 4. 删除孤立 Posting =====
            self.stdout.write("🧹 清理孤立 postings ...")
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM postings WHERE term_id NOT IN (SELECT id FROM terms);"
                )

            # ===== 5. 最终再算一次 DF，保证一致 =====
            self.stdout.write("📏 最终 DF 校正 ...")
            for term in Term.objects.all():
                df = (
                    Posting.objects
                    .filter(term_id=term.id)
                    .values("book_id")
                    .distinct()
                    .count()
                )
                term.df = df
                term.save()

            # ===== 6. 统计信息 =====
            avg_len = total_len / total_docs
            IndexStat.objects.update_or_create(
                key="N_docs", defaults={"value": str(total_docs)}
            )
            IndexStat.objects.update_or_create(
                key="avg_doc_len", defaults={"value": str(avg_len)}
            )

        self.stdout.write(self.style.SUCCESS("🎉 倒排索引构建完成"))
        self.stdout.write(f"📊 文档数: {total_docs}, 平均长度: {avg_len:.2f} tokens")
        self.stdout.write(f"📚 词典大小: {Term.objects.count()} 个 term")
