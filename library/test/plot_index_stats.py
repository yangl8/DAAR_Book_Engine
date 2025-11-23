import pandas as pd
import matplotlib.pyplot as plt
import os

# ===============================
# 路径设置
# ===============================

BASE_DIR = "test"
CSV_BOOK = os.path.join(BASE_DIR, "index_book_stats.csv")
CSV_VOCAB = os.path.join(BASE_DIR, "vocab_stats.csv")

OUT_DIR = os.path.join(BASE_DIR, "graph")
os.makedirs(OUT_DIR, exist_ok=True)

# ===============================
# 读取数据
# ===============================
book_df = pd.read_csv(CSV_BOOK)
vocab_df = pd.read_csv(CSV_VOCAB)


# ===============================
# 图 1：文档长度直方图（token_count）
# ===============================
plt.figure(figsize=(8, 5))
plt.hist(book_df["token_count"], bins=50, edgecolor='black')
plt.title("Distribution des longueurs de documents (token_count)")
plt.xlabel("Nombre de tokens")
plt.ylabel("Fréquence")
plt.grid(alpha=0.3)

out1 = os.path.join(OUT_DIR, "token_count_hist.png")
plt.savefig(out1, dpi=300)
plt.close()
print(f"图 1 已生成: {out1}")


# ===============================
# 图 2：DF 分布直方图
# ===============================

plt.figure(figsize=(8, 5))
plt.hist(vocab_df["df"], bins=50, edgecolor='black')
plt.title("Distribution de DF (Document Frequency)")
plt.xlabel("DF (nombre de documents contenant le terme)")
plt.ylabel("Fréquence")
plt.grid(alpha=0.3)

out2 = os.path.join(OUT_DIR, "df_hist.png")
plt.savefig(out2, dpi=300)
plt.close()
print(f"图 2 已生成: {out2}")


# ===============================
# 图 3：TF-IDF 稀疏性直方图 sparsity_percent
# ===============================

plt.figure(figsize=(8, 5))
plt.hist(book_df["sparsity_percent"], bins=50, edgecolor='black')
plt.title("Distribution de la sparsité TF–IDF (%)")
plt.xlabel("Sparsité (%)")
plt.ylabel("Fréquence")
plt.grid(alpha=0.3)

out3 = os.path.join(OUT_DIR, "sparsity_hist.png")
plt.savefig(out3, dpi=300)
plt.close()
print(f"图 3 已生成: {out3}")


print("\n🎉 所有图表生成完毕！")
