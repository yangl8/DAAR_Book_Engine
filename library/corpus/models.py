from django.db import models

# 1️⃣ 每本书的信息与正文
class Book(models.Model):
    text_id = models.IntegerField(primary_key=True)  # URL 后缀 / Text#
    title = models.TextField(blank=True, default="")
    authors = models.TextField(blank=True, default="")
    local_path = models.TextField(blank=True, default="")

    # front_matter = models.TextField(blank=True, default="")  # START 前
    # body_text = models.TextField(blank=True, default="")      # START…END（去除 license）

    doc_len_tokens = models.IntegerField(default=0)           # 分词后长度（BM25 用）

    class Meta:
        db_table = "books"


# 2️⃣ 唯一词表
class Term(models.Model):
    term = models.TextField(unique=True)
    df = models.IntegerField(default=0)                       # 在多少本书中出现

    class Meta:
        db_table = "terms"
        indexes = [models.Index(fields=["term"])]


# 3️⃣ 倒排索引
class Posting(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    tf = models.IntegerField(default=0)                       # term 在该书中出现次数
    # positions = models.TextField(blank=True, default="")       # term 出现位置列表（JSON）

    class Meta:
        db_table = "postings"
        unique_together = (("term", "book"),)


# 4️⃣ 全局统计信息
class IndexStat(models.Model):
    key = models.TextField(primary_key=True)
    value = models.TextField()

    class Meta:
        db_table = "index_stats"
