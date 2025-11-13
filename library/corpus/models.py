from django.db import models

# 1️⃣ 书籍基本信息
class Book(models.Model):
    text_id = models.IntegerField(primary_key=True)
    title = models.TextField(blank=True, default="")
    authors = models.TextField(blank=True, default="")
    local_path = models.TextField(blank=True, default="")
    doc_len_tokens = models.IntegerField(default=0)

    class Meta:
        db_table = "books"


# 2️⃣ 词项表（唯一）
class Term(models.Model):
    term = models.TextField(unique=True)
    df = models.IntegerField(default=0)

    class Meta:
        db_table = "terms"
        indexes = [models.Index(fields=["term"])]


# 3️⃣ Posting（倒排索引）
class Posting(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    tf = models.IntegerField(default=0)
    tfidf = models.FloatField(default=0.0)

    class Meta:
        db_table = "postings"
        unique_together = (("term", "book"),)


# 4️⃣ 全局统计（N_docs、avg_len 等）
class IndexStat(models.Model):
    key = models.TextField(primary_key=True)
    value = models.TextField()

    class Meta:
        db_table = "index_stats"
