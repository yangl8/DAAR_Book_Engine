import pandas as pd
import matplotlib.pyplot as plt
import os

# ======================================
# 路径设置
# ======================================

BASE_DIR = "test"
CSV_SIM = os.path.join(BASE_DIR, "similarity.csv")

OUT_DIR = os.path.join(BASE_DIR, "graph")
os.makedirs(OUT_DIR, exist_ok=True)

# ======================================
# 加载数据
# ======================================

print("Loading similarity data...")
sim_df = pd.read_csv(CSV_SIM)

if "similarity" not in sim_df.columns:
    raise ValueError("CSV file must contain a 'similarity' column.")

print(f"Loaded {len(sim_df)} similarity entries.")

# ======================================
# 绘图：余弦相似度分布
# ======================================

plt.figure(figsize=(8, 5))
plt.hist(sim_df["similarity"], bins=50, edgecolor='black')
plt.title("Distribution of Cosine Similarity Between Documents")
plt.xlabel("Cosine Similarity")
plt.ylabel("Frequency")
plt.grid(alpha=0.3)

out_path = os.path.join(OUT_DIR, "similarity_hist.png")
plt.savefig(out_path, dpi=300)
plt.close()

print(f"Similarity histogram saved to: {out_path}")
print("Done.")
