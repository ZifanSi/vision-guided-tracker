#!/usr/bin/env python3
"""
Plot PR curve and epoch metrics from Ultralytics results.csv

Usage:
  python yolo_metrics_plots.py --csv results.csv --outdir plots --smooth 7 --show
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def pick(df, candidates):
    for c in candidates:
        if c in df.columns: 
            return c
    # fallback by suffix match (handles case variants)
    lc = {c.lower(): c for c in df.columns}
    for c in candidates:
        k = c.lower()
        if k in lc: 
            return lc[k]
    # fuzzy endswith for YOLO variants
    for col in df.columns:
        if any(col.lower().endswith(x.lower()) for x in candidates):
            return col
    raise KeyError(f"None of columns found: {candidates}")

def smooth_series(x, win):
    if win <= 1:
        return x
    win = int(max(1, win))
    w = np.ones(win) / win
    return np.convolve(x, w, mode="same")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to Ultralytics results.csv")
    ap.add_argument("--outdir", default="plots", help="Output directory for images")
    ap.add_argument("--smooth", type=int, default=1, help="Moving-average window (epochs)")
    ap.add_argument("--show", action="store_true", help="Show figures")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)

    # Columns (YOLOv5/8/11 usually match these)
    epoch_col = pick(df, ["epoch"])
    p_col  = pick(df, ["metrics/precision(B)", "metrics/precision"])
    r_col  = pick(df, ["metrics/recall(B)", "metrics/recall"])
    m50_col    = pick(df, ["metrics/mAP50(B)", "metrics/mAP50"])
    m5095_col  = pick(df, ["metrics/mAP50-95(B)", "metrics/mAP50-95"])

    epoch = df[epoch_col].to_numpy()
    P = df[p_col].astype(float).to_numpy()
    R = df[r_col].astype(float).to_numpy()
    m50 = df[m50_col].astype(float).to_numpy()
    m5095 = df[m5095_col].astype(float).to_numpy()
    F1 = 2 * (P * R) / (P + R + 1e-12)

    # Optional smoothing for epoch curves
    sw = max(1, args.smooth)
    Ps, Rs, F1s, m50s, m5095s = (smooth_series(P, sw),
                                 smooth_series(R, sw),
                                 smooth_series(F1, sw),
                                 smooth_series(m50, sw),
                                 smooth_series(m5095, sw))

    # Best-F1 epoch (unsmoothed for correctness)
    best_idx = int(np.nanargmax(F1))
    best_info = dict(epoch=int(epoch[best_idx]), P=P[best_idx], R=R[best_idx], F1=F1[best_idx])

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    # 1) Precision vs Recall curve
    plt.figure(figsize=(7, 6))
    plt.plot(P, R, linewidth=2)
    plt.scatter([P[best_idx]], [R[best_idx]], s=60)
    plt.title("Precision vs Recall")
    plt.xlabel("Precision"); plt.ylabel("Recall")
    plt.xlim(0, 1); plt.ylim(0, 1)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.text(P[best_idx], R[best_idx],
             f"  best F1={best_info['F1']:.3f}\n  P={best_info['P']:.3f}, R={best_info['R']:.3f}\n  epoch={best_info['epoch']}",
             va="bottom", ha="left")
    pr_path = outdir / "precision_vs_recall.png"
    plt.savefig(pr_path, bbox_inches="tight", dpi=200)

    # 2) Metrics over epoch (Precision, Recall, F1, mAP50, mAP50-95)
    fig, axes = plt.subplots(3, 2, figsize=(11, 10))
    ax = axes.ravel()

    def line(ax, y, label):
        ax.plot(epoch, y, linewidth=1.8, label=label)
        ax.set_xlabel("Epoch"); ax.set_ylabel(label)
        ax.grid(True, linestyle="--", alpha=0.3)

    line(ax[0], Ps, "Precision")
    line(ax[1], Rs, "Recall")
    line(ax[2], F1s, "F1")
    line(ax[3], m50s, "mAP50")
    line(ax[4], m5095s, "mAP50-95")

    # Best-F1 marker on F1 subplot
    ax[2].scatter([epoch[best_idx]], [F1[best_idx]], s=40)
    ax[2].set_title(f"F1 (best={F1[best_idx]:.3f} @ epoch {epoch[best_idx]})")

    # Hide the unused 6th cell
    ax[5].axis("off")

    fig.suptitle("Training Metrics over Epoch", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    metrics_path = outdir / "metrics_over_epoch.png"
    fig.savefig(metrics_path, bbox_inches="tight", dpi=200)

    print(f"[OK] Saved: {pr_path}")
    print(f"[OK] Saved: {metrics_path}")
    print(f"Best F1={F1[best_idx]:.4f} at epoch={epoch[best_idx]} (P={P[best_idx]:.4f}, R={R[best_idx]:.4f})")

    if args.show:
        plt.show()

if __name__ == "__main__":
    main()
