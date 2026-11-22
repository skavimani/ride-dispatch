"""Draw the report figures from results/*.json (needs matplotlib).

Run:  python3 -m benchmarks.make_charts
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .common import load, RESULTS

# fixed categorical order (validated default palette, light mode)
C = {"phase2": "#2a78d6", "csr_first": "#eb6834", "astar": "#1baf7a",
     "cached": "#eda100", "batch": "#e87ba4"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a65", "#e3e2dc"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.grid.axis": "y",
    "legend.frameon": False, "axes.titlesize": 9.5, "axes.titleweight": "bold",
    "axes.titlelocation": "left",
})


def figure_scaling():
    rt = load("routing")["400"]
    ix = load("index")
    sim = load("simulation")["scale"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.1))

    ax = axes[0]
    sides = list(rt)
    V = [rt[s]["V"] / 1000 for s in sides]
    for key, label, mk in (("phase2", "Phase 2 Dijkstra", "o"), ("csr_first", "CSR + first-hit", "s"),
                           ("astar", "CSR + first-hit + A*", "^"), ("cached", "Route cache", "D")):
        ax.plot(V, [rt[s][key]["ms"] for s in sides], marker=mk, ms=5, lw=2,
                color=C[key], label=label)
    ax.set_yscale("log")
    ax.set_xlabel("Intersections (thousands)")
    ax.set_ylabel("ms per request (log scale)")
    ax.set_title("(a) Road-time search, sparse drivers")
    ax.legend(fontsize=7.5, loc="center right")

    ax = axes[1]
    ns = list(ix)
    x = range(len(ns))
    w = 0.38
    ax.bar([i - w / 2 for i in x], [ix[n]["kdtree"]["update_us"] for n in ns], w - 0.03,
           color=C["phase2"], label="k-d tree (Phase 2)")
    ax.bar([i + w / 2 for i in x], [ix[n]["grid"]["update_us"] for n in ns], w - 0.03,
           color=C["csr_first"], label="Uniform grid (Phase 3)")
    for i, n in zip(x, ns):
        for dx, key in ((-w / 2, "kdtree"), (w / 2, "grid")):
            v = ix[n][key]["update_us"]
            ax.text(i + dx, v + 0.15, f"{v:.1f}", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(list(x), [f"{int(n):,}" for n in ns])
    ax.set_xlabel("Free drivers")
    ax.set_ylabel("µs per GPS update")
    ax.set_title("(b) Driver location updates")
    ax.legend(fontsize=7.5, loc="upper left")

    ax = axes[2]
    sides = list(sim)
    V = [sim[s]["V"] / 1000 for s in sides]
    ax.plot(V, [sim[s]["phase2"]["dispatch_ms_per_match"] for s in sides], marker="o", ms=5,
            lw=2, color=C["phase2"], label="Phase 2")
    ax.plot(V, [sim[s]["grid+A*"]["dispatch_ms_per_match"] for s in sides], marker="^", ms=5,
            lw=2, color=C["astar"], label="Phase 3 (grid + A*)")
    ax.set_xlabel("Intersections (thousands)")
    ax.set_ylabel("Dispatch ms per matched ride")
    ax.set_ylim(bottom=0)
    ax.set_title("(c) End-to-end, 10-min simulation")
    ax.legend(fontsize=7.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, "fig_scaling.png"), dpi=220)


def figure_simulation():
    sim = load("simulation")["detail"]
    cfgs = [("phase2", "Phase 2", C["phase2"]), ("grid+A*", "Grid + A*", C["astar"]),
            ("cached", "Grid + cache", C["cached"]), ("batch", "Batch (Hungarian)", C["batch"])]
    fig, axes = plt.subplots(1, 2, figsize=(10, 2.9))
    ax = axes[0]
    w = 0.2
    for j, (key, label, col) in enumerate(cfgs):
        vals = [sim[s][key]["dispatch_ms_per_match"] for s in ("normal", "rush")]
        xs = [i + (j - 1.5) * w for i in range(2)]
        ax.bar(xs, vals, w - 0.02, color=col, label=label)
        for xx, v in zip(xs, vals):
            ax.text(xx, v + 0.15, f"{v:.2f}" if v < 1 else f"{v:.1f}", ha="center", fontsize=7, color=INK)
    ax.set_xticks([0, 1], ["Normal (~70% of capacity)", "Rush hour (~140%)"])
    ax.set_ylabel("Dispatch ms per matched ride")
    ax.set_title("(a) Computing cost, 40,000-intersection city, 30 min")
    ax.legend(fontsize=7.5, ncol=2, loc="upper left")

    ax = axes[1]
    r = sim["rush"]
    for j, (key, label, col) in enumerate(cfgs):
        vals = [r[key]["mean_eta_s"] / 60, r[key]["p95_eta_s"] / 60]
        xs = [i + (j - 1.5) * w for i in range(2)]
        ax.bar(xs, vals, w - 0.02, color=col, label=label)
        for xx, v in zip(xs, vals):
            ax.text(xx, v + 0.4, f"{v:.1f}", ha="center", fontsize=7, color=INK)
    ax.set_xticks([0, 1], ["Mean pickup time", "95th-percentile pickup time"])
    ax.set_ylabel("Minutes")
    ax.set_title("(b) Rider pickup time, rush hour")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, "fig_simulation.png"), dpi=220)


if __name__ == "__main__":
    figure_scaling()
    figure_simulation()
    print("figures written to", RESULTS)
