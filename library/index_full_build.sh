#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "📦 删除旧的索引数据库..."
rm -f db_index.sqlite3

echo "📚 [1/4] migrate 新数据库结构..."
python manage.py migrate --settings=library.settings_index --noinput

echo "🔧 修复/添加 postings.tfidf 字段（如果缺失）..."
sqlite3 db_index.sqlite3 "ALTER TABLE postings ADD COLUMN tfidf REAL DEFAULT 0.0;" 2>/dev/null || true

echo "🚀 [2/4] 构建倒排索引 (TopK=3000 TF + 词干) ..."
python manage.py index_build_fast \
  --settings=library.settings_index \
  --meta ../selected_meta.csv \
  --dir ../books_html_kept \
  --topk 3000

echo "🔧 再次确保 postings.tfidf 字段存在..."
sqlite3 db_index.sqlite3 "ALTER TABLE postings ADD COLUMN tfidf REAL DEFAULT 0.0;" 2>/dev/null || true

echo "🧮 [3/4] 计算 TF-IDF..."
python manage.py index_compute_tfidf --settings=library.settings_index

echo "✂️ [4/4] 按 TF-IDF 精剪 (TopK=2500)..."
python manage.py index_prune_tfidf \
  --settings=library.settings_index \
  --topk 2500

#echo "🎉 完成！索引数据库已生成：db_index.sqlite3"
echo "=============================="
echo " 5/7 构建文档向量 build_doc_vectors"
echo "=============================="
python manage.py build_doc_vectors \
  --settings=library.settings_index

echo "=============================="
echo "6/7 构建文档图 build_doc_graph"
echo "=============================="
python manage.py build_doc_graph \
  --settings=library.settings_index

echo "=============================="
echo "7/7 计算中心性 compute_centrality"
echo "=============================="
python manage.py compute_centrality \
  --settings=library.settings_index

echo "=============================="
echo "🎉 完成！索引数据库已生成：db_index.sqlite3"
echo "=============================="