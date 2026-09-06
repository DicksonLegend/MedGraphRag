# journal_paper/figures/make_fig_arch.py  (Connected architecture — Fig 1)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

plt.rcParams["font.family"] = "DejaVu Sans"
fig, ax = plt.subplots(figsize=(12.5, 9.0), dpi=300)
ax.set_xlim(0, 120); ax.set_ylim(6, 88); ax.axis("off")

class Box:
    def __init__(self, cx, cy, lines, fs=7.0, pad_x=2.4, pad_y=2.0, min_w=None, min_h=None):
        self.cx = cx
        self.cy = cy
        self.lines = lines
        self.fs = fs
        calc_w = max(len(l) for l in lines) * 0.076 * fs + pad_x
        calc_h = len(lines) * 0.22 * fs + pad_y
        self.w = max(calc_w, min_w) if min_w else calc_w
        self.h = max(calc_h, min_h) if min_h else calc_h
        self.left = cx - self.w / 2
        self.right = cx + self.w / 2
        self.bottom = cy - self.h / 2
        self.top = cy + self.h / 2

    def draw(self, ax, ls="-", ec="k", fc="white", lw=0.9):
        ax.add_patch(Rectangle((self.left, self.bottom), self.w, self.h,
                               fc=fc, ec=ec, lw=lw, ls=ls, zorder=2))
        ax.text(self.cx, self.cy, "\n".join(self.lines), ha="center", va="center",
                fontsize=self.fs, linespacing=1.32, zorder=3)

    @property
    def pt_left(self): return (self.left, self.cy)
    @property
    def pt_right(self): return (self.right, self.cy)
    @property
    def pt_top(self): return (self.cx, self.top)
    @property
    def pt_bottom(self): return (self.cx, self.bottom)
    def top_at(self, x): return (x, self.top)
    def bottom_at(self, x): return (x, self.bottom)
    def left_at(self, y): return (self.left, y)
    def right_at(self, y): return (self.right, y)

def arrow(p1, p2, lab=None, at=None, fs=6.4, lw=0.85):
    ax.annotate("", xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle="-|>", lw=lw, color="k",
                                shrinkA=0, shrinkB=0, mutation_scale=9), zorder=1)
    if lab:
        if at is None:
            at = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 1.2)
        ax.text(at[0], at[1], lab, fontsize=fs, ha="center", va="center",
                bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"), zorder=4)

def poly_arrow(pts, lab=None, at=None, fs=6.4, lw=0.85):
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], lw=lw, color="k", zorder=1)
    ax.annotate("", xy=pts[-1], xytext=pts[-2],
                arrowprops=dict(arrowstyle="-|>", lw=lw, color="k",
                                shrinkA=0, shrinkB=0, mutation_scale=9), zorder=1)
    if lab and at:
        ax.text(at[0], at[1], lab, fontsize=fs, ha="center", va="center",
                bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"), zorder=4)

# ── OFFLINE BAND ──
ax.text(2, 85.5, "Offline knowledge-base construction", fontsize=8.5, fontweight="bold")
corpus = Box(60, 80.5, ["Clinical corpus", "(guidelines, PubMed/PMC, MedQA textbooks, drug refs)"], fs=7.0)
chunking = Box(60, 71.5, ["Passage chunking", "2,294,038 chunks (~512 tokens)"], fs=7.0)
faiss = Box(30, 60.5, ["MedCPT encoder + FAISS IVF-PQ", "(2.29M vectors)"], fs=6.8)
kuzu = Box(86, 60.5, ["UMLS negation/temporal extraction", "+ Kuzu property graph",
                     "(2.50M nodes; 632,931", "NEGATES / TEMPORAL edges)"], fs=6.4)

corpus.draw(ax); chunking.draw(ax); faiss.draw(ax); kuzu.draw(ax)
arrow(corpus.pt_bottom, chunking.pt_top)
arrow(chunking.bottom_at(chunking.cx - 10), faiss.pt_top)
arrow(chunking.bottom_at(chunking.cx + 10), kuzu.pt_top)

# Boundary line
ax.plot([0, 120], [53.5, 53.5], ls=":", lw=0.8, color="gray")
ax.text(118, 54.3, "offline / online boundary", fontsize=6.2, color="gray", ha="right")

# ── ONLINE BAND ──
ax.text(2, 51.5, "Online inference (fully offline device)", fontsize=8.5, fontweight="bold")
query = Box(6.5, 43.0, ["Clinical", "query"], fs=7.0)
stage1 = Box(22.0, 43.0, ["Stage 1 · Query rewriting", "Qwen2.5-7B, T=0.0", "<=30-word canonical form"], fs=6.8)

# Retrieval stack with matched width
ret_w = 18.0
stage2 = Box(48.0, 49.0, ["Stage 2 · Dense retrieval", "(MedCPT + FAISS)"], fs=6.8, min_w=ret_w)
lexical = Box(48.0, 43.0, ["Lexical retrieval", "(BM25)"], fs=6.8, min_w=ret_w)
stage3 = Box(48.0, 37.0, ["Stage 3 · Graph expansion", "(Kuzu, <=2 hops)"], fs=6.8, min_w=ret_w)

rrf = Box(70.5, 43.0, ["RRF fusion +", "relation-aware rerank", "(gamma = 0.15)"], fs=6.8)
top10 = Box(89.0, 43.0, ["Top-10 evidence", "passages"], fs=6.8)

query.draw(ax); stage1.draw(ax)
stage2.draw(ax); lexical.draw(ax); stage3.draw(ax)
rrf.draw(ax); top10.draw(ax)

# Query & Stage 1 connections
arrow(query.pt_right, stage1.pt_left)
arrow(stage1.right_at(stage1.cy + 1.8), stage2.pt_left)
arrow(stage1.pt_right, lexical.pt_left)
arrow(stage1.right_at(stage1.cy - 1.8), stage3.pt_left)

# Retrieval to RRF
arrow(stage2.pt_right, rrf.left_at(rrf.cy + 2.0))
arrow(lexical.pt_right, rrf.pt_left)
arrow(stage3.pt_right, rrf.left_at(rrf.cy - 2.0))
arrow(rrf.pt_right, top10.pt_left)

# Cross-boundary FAISS -> Stage 2 (with comfortable clearance above stage 2 top)
y_bridge_faiss = 52.6
poly_arrow([faiss.pt_bottom, (faiss.cx, y_bridge_faiss), (stage2.cx, y_bridge_faiss), stage2.pt_top])

# ── STAGE 4 CONTAINER ──
c_left, c_right = 62.0, 106.0
c_bottom, c_top = 18.2, 31.8
ax.add_patch(Rectangle((c_left, c_bottom), c_right - c_left, c_top - c_bottom,
                       fill=False, ec="k", ls="--", lw=0.9, zorder=1))
ax.text(c_left + 1.5, c_top - 1.8, "Stage 4 · Beta-gated verification", fontsize=7.2, fontweight="bold")

faith = Box(73.5, 26.5, ["Evidence faithfulness", "(NLI phi)"], fs=6.6)
consist = Box(94.5, 26.5, ["Graph consistency", "(S_g)"], fs=6.6)
v_box = Box(84.0, 21.0, [r"V = $\beta\varphi$ + (1$-\beta$)S_g $\geq \tau^{*}$   (WAR $\leq$ 10%)"], fs=6.5)

faith.draw(ax); consist.draw(ax); v_box.draw(ax)

# Top-10 to Evidence Faithfulness
poly_arrow([top10.pt_bottom, (top10.cx, 34.5), (faith.cx, 34.5), faith.pt_top])

# Kuzu -> Graph consistency (S_g) via far right margin
poly_arrow([(kuzu.right, kuzu.cy + 1.0), (110.0, kuzu.cy + 1.0), (110.0, consist.cy), consist.pt_right])

# Faithfulness & Consistency to V
arrow(faith.pt_bottom, v_box.top_at(faith.cx))
arrow(consist.pt_bottom, v_box.top_at(consist.cx))

# Cross-boundary Kuzu -> Stage 3 (via horizontal bridge at y=33.2 with arc jump over faith drop at x=73.5)
ax.plot([kuzu.right, 102.5], [kuzu.cy - 1.0, kuzu.cy - 1.0], lw=0.85, color="k", zorder=1)
ax.plot([102.5, 102.5], [kuzu.cy - 1.0, 33.2], lw=0.85, color="k", zorder=1)

# Horizontal line with bridge jump over x=73.5
jump_x = faith.cx
r_jump = 0.85
ax.plot([102.5, jump_x + r_jump], [33.2, 33.2], lw=0.85, color="k", zorder=1)
theta = np.linspace(0, np.pi, 50)
ax.plot(jump_x + r_jump * np.cos(theta), 33.2 + r_jump * np.sin(theta), lw=0.85, color="k", zorder=5)
ax.plot([jump_x - r_jump, stage3.cx], [33.2, 33.2], lw=0.85, color="k", zorder=1)
ax.annotate("", xy=stage3.pt_bottom, xytext=(stage3.cx, 33.2),
            arrowprops=dict(arrowstyle="-|>", lw=0.85, color="k", shrinkA=0, shrinkB=0, mutation_scale=9), zorder=1)

# ── OUTPUTS (BOTTOM ROW) ──
stage5 = Box(74.0, 11.8, ["Stage 5 · Evidence-grounded generation", "(Qwen2.5-7B Q4_K_M, single-flight GPU lock)"], fs=6.8)
response = Box(105.0, 11.8, ["Verified clinical response [E#]", "+/- F1 cross-modal alert", "-> human review"], fs=6.3)
refusal = Box(32.0, 11.8, ["Structured refusal +", "knowledge-gap card (F2)"], fs=6.8)

stage5.draw(ax); response.draw(ax); refusal.draw(ax)

# Stage 4 to Stage 5 (V >= tau*)
arrow(v_box.bottom_at(stage5.cx), stage5.pt_top, lab=r"V $\geq \tau^{*}$", at=(stage5.cx + 4.5, 15.6))

# Stage 5 to Verified Response
arrow(stage5.pt_right, response.pt_left)

# Stage 4 to Structured Refusal (V < tau*)
poly_arrow([v_box.left_at(v_box.cy), (53.5, v_box.cy), (53.5, refusal.cy), refusal.pt_right],
           lab=r"V $< \tau^{*}$", at=(58.0, v_box.cy + 1.4))

plt.tight_layout()
plt.savefig("fig_arch.pdf", bbox_inches="tight")
plt.savefig("fig_arch.png", dpi=300, bbox_inches="tight")
print("saved")