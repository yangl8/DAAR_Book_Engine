#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "📐 6/7 构建文档向量 build_doc_vectors"
echo "=============================="
python manage.py build_doc_vectors \
  --settings=library.settings_index

echo "=============================="
echo "🕸️ 7/7 构建文档图 build_doc_graph"
echo "=============================="
python manage.py build_doc_graph \
  --settings=library.settings_index

echo "=============================="
echo "📊 8/7 计算中心性 compute_centrality"
echo "=============================="
python manage.py compute_centrality \
  --settings=library.settings_index

echo "=============================="
echo "🎉 全部完成！最终数据库 = db_index.sqlite3"
echo "=============================="