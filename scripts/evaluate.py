"""Evaluate the saved artifact on the test split and draw every figure used by the report and slides.

Reads artifacts/ and reports/train_report.json (written by train.py), recomputes the test metrics
from the artifact itself, then writes reports/metrics.json and reports/figures/*.png (150 dpi).

Run:  python scripts/evaluate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.train import (  # noqa: E402
    METADATA_PATH,
    MODEL_PATH,
    REPORT_DIR,
    TRAIN_REPORT_PATH,
    clinical_metrics,
    load_data,
    malignant_proba,
    split,
)

FIG_DIR = REPORT_DIR / "figures"
METRICS_PATH = REPORT_DIR / "metrics.json"
DPI = 150

# Red / blue pass the colour-blind check (red / green does not); the rose accent marks the threshold.
MALIGNANT_COLOR = "#C92A2A"
BENIGN_COLOR = "#1971C2"
ACCENT = "#C2255C"
INK = "#1F2937"
MUTED = "#6B7280"
CLASS_COLORS = {0: MALIGNANT_COLOR, 1: BENIGN_COLOR}
CLASS_VI = {0: "Ác tính (malignant)", 1: "Lành tính (benign)"}

plt.rcParams.update({
    "figure.dpi": DPI, "savefig.dpi": DPI, "font.size": 10.5, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.edgecolor": "#C9CED8", "axes.labelcolor": INK, "axes.grid": True, "grid.color": "#ECEEF3",
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "font.family": "DejaVu Sans",
})


def save(fig, name: str) -> str:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return name


# ---------------------------------------------------------------- data

def class_balance(y) -> str:
    counts = [int(np.sum(y == 0)), int(np.sum(y == 1))]
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    bars = ax.bar([CLASS_VI[0], CLASS_VI[1]], counts, color=[MALIGNANT_COLOR, BENIGN_COLOR], width=0.55)
    for bar, c in zip(bars, counts, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, c + 6, f"{c} ({c / len(y):.1%})", ha="center", color=INK)
    ax.set_ylabel("Số mẫu")
    ax.set_ylim(0, max(counts) * 1.18)
    ax.set_title(f"Phân bố nhãn — {len(y)} mẫu")
    ax.grid(axis="x", visible=False)
    return save(fig, "01_phan_bo_nhan.png")


def feature_distributions(X, y, names) -> str:
    picks = ["mean radius", "mean texture", "worst concave points", "worst area", "mean smoothness", "worst perimeter"]
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.8))
    for ax, feat in zip(axes.flat, picks, strict=True):
        col = X[:, names.index(feat)]
        bins = np.histogram_bin_edges(col, bins=25)
        for cls in (1, 0):
            ax.hist(col[y == cls], bins=bins, alpha=0.6, color=CLASS_COLORS[cls], label=CLASS_VI[cls])
        ax.set_title(feat, fontsize=10.5)
        ax.set_ylabel("Số mẫu")
    axes.flat[0].legend(fontsize=9)
    fig.suptitle("Phân phối một số đặc trưng theo nhãn", fontweight="bold")
    return save(fig, "02_phan_phoi_dac_trung.png")


def correlation(X, names) -> str:
    idx = [i for i, n in enumerate(names) if n.startswith("mean ")]
    corr = np.corrcoef(X[:, idx], rowvar=False)
    labels = [names[i].removeprefix("mean ") for i in idx]
    fig, ax = plt.subplots(figsize=(7.4, 6.2))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(idx)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(idx)), labels)
    ax.grid(False)
    for i in range(len(idx)):
        for j in range(len(idx)):
            ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(corr[i, j]) > 0.6 else INK)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Hệ số tương quan Pearson")
    ax.set_title("Tương quan giữa 10 đặc trưng nhóm mean")
    return save(fig, "03_tuong_quan.png")


def pca_plot(X, y) -> tuple[str, list[float]]:
    pca = PCA(n_components=2)
    comps = pca.fit_transform(StandardScaler().fit_transform(X))
    ev = [float(v) for v in pca.explained_variance_ratio_]
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    for cls, marker in ((1, "o"), (0, "^")):
        m = y == cls
        ax.scatter(comps[m, 0], comps[m, 1], s=22, alpha=0.75, color=CLASS_COLORS[cls], marker=marker,
                   edgecolor="white", linewidth=0.4, label=CLASS_VI[cls])
    ax.set_xlabel(f"PC1 ({ev[0]:.1%} phương sai)")
    ax.set_ylabel(f"PC2 ({ev[1]:.1%} phương sai)")
    ax.set_title(f"PCA 2 chiều của 30 đặc trưng chuẩn hoá — giữ {sum(ev):.1%} phương sai")
    ax.legend()
    return save(fig, "04_pca.png"), ev


# ---------------------------------------------------------------- training choices

def grid_heatmap(report) -> str:
    rows = report["grid_search"]["results"]
    Cs = sorted({r["C"] for r in rows})
    gammas = ["scale", 0.001, 0.01, 0.1]
    grid = np.array([[next(r["mean"] for r in rows if r["C"] == c and r["gamma"] == g) for g in gammas] for c in Cs])
    best = report["grid_search"]["best_params"]
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    im = ax.imshow(grid, cmap="Purples", vmin=grid.min() - 0.01, vmax=1)
    ax.set_xticks(range(len(gammas)), [str(g) for g in gammas])
    ax.set_yticks(range(len(Cs)), [str(c) for c in Cs])
    ax.set_xlabel("gamma")
    ax.set_ylabel("C")
    ax.grid(False)
    for i, c in enumerate(Cs):
        for j, g in enumerate(gammas):
            is_best = c == best["svc__C"] and g == best["svc__gamma"]
            ax.text(j, i, f"{grid[i, j]:.4f}", ha="center", va="center", fontsize=9,
                    color="white" if grid[i, j] > (grid.min() + 1) / 2 else INK,
                    fontweight="bold" if is_best else "normal")
            if is_best:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=ACCENT, linewidth=2.5))
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="recall_macro (CV 5-fold)")
    ax.set_title("GridSearchCV: recall_macro trung bình theo C và gamma")
    return save(fig, "05_grid_search.png")


def calibration_comparison(report) -> str:
    rows = report["calibration"]["candidates"]
    chosen = report["calibration"]["chosen"]
    names = [r["method"] for r in rows]
    values = [r["brier"] for r in rows]
    colors = [ACCENT if n == chosen else ("#ADB5BD" if r["deprecated"] else "#B197C7")
              for n, r in zip(names, rows, strict=True)]
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    bars = ax.barh(range(len(rows)), values, color=colors, height=0.55)
    ax.set_yticks(range(len(rows)), [n + (" (deprecated)" if r["deprecated"] else "") for n, r in
                                     zip(names, rows, strict=True)])
    ax.invert_yaxis()
    for bar, v in zip(bars, values, strict=True):
        ax.text(v + max(values) * 0.01, bar.get_y() + bar.get_height() / 2, f"{v:.5f}", va="center", color=INK)
    ax.set_xlim(0, max(values) * 1.2)
    ax.set_xlabel("Brier score trên xác suất out-of-fold (thấp hơn là tốt hơn)")
    ax.set_title("So sánh cách hiệu chỉnh xác suất")
    ax.grid(axis="y", visible=False)
    return save(fig, "06_hieu_chinh_xac_suat.png")


def threshold_curve(report) -> str:
    y = np.array(report["oof"]["y_true"])
    p = np.array(report["oof"]["proba_malignant"])
    thr = report["threshold"]["value"]
    target = report["threshold"]["target_sensitivity"]
    grid = np.linspace(0.01, 0.99, 197)
    sens = [np.mean(p[y == 0] >= t) for t in grid]
    spec = [np.mean(p[y == 1] < t) for t in grid]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(grid, sens, color=MALIGNANT_COLOR, lw=2, label="Sensitivity (bắt được ca ác tính)")
    ax.plot(grid, spec, color=BENIGN_COLOR, lw=2, label="Specificity (nhận đúng ca lành tính)")
    ax.axhline(target, color=MUTED, lw=1, ls=":", label=f"Mục tiêu sensitivity {target:.2f}")
    ax.axvline(thr, color=ACCENT, lw=1.8, ls="--", label=f"Ngưỡng chọn {thr:.4f}")
    ax.axvline(0.5, color="#ADB5BD", lw=1, ls="-.", label="Ngưỡng mặc định 0,5")
    ax.set_xlabel("Ngưỡng trên P(ác tính)")
    ax.set_ylabel("Tỷ lệ")
    ax.set_ylim(0.8, 1.005)
    ax.set_title("Chọn ngưỡng trên xác suất out-of-fold của tập train")
    ax.legend(loc="lower center", fontsize=8.5)
    return save(fig, "07_chon_nguong.png")


# ---------------------------------------------------------------- test results

def confusion(test) -> str:
    cm = np.array(test["confusion_matrix"])
    labels = ["Ác tính", "Lành tính"]
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    ax.imshow(cm, cmap="Purples", vmin=0, vmax=cm.max() * 1.15)
    ax.set_xticks([0, 1], labels)
    ax.set_yticks([0, 1], labels)
    ax.set_xlabel("Dự đoán")
    ax.set_ylabel("Thực tế")
    ax.grid(False)
    names = [["TP", "FN"], ["FP", "TN"]]
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]}\n{names[i][j]}", ha="center", va="center", fontsize=13,
                    color="white" if cm[i, j] > cm.max() * 0.5 else INK, fontweight="bold")
    ax.set_title(f"Ma trận nhầm lẫn — test, ngưỡng {test['threshold']:.4f}")
    return save(fig, "08_ma_tran_nham_lan.png")


def roc_pr(y_test, proba, test) -> str:
    y_pos = (y_test == 0).astype(int)
    fpr, tpr, _ = roc_curve(y_pos, proba)
    prec, rec, _ = precision_recall_curve(y_pos, proba)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.2))
    a1.plot(fpr, tpr, color=ACCENT, lw=2, label=f"ROC-AUC = {test['roc_auc']:.4f}")
    a1.plot([0, 1], [0, 1], color="#ADB5BD", lw=1, ls="--", label="Đoán ngẫu nhiên")
    a1.scatter([1 - test["specificity"]], [test["sensitivity"]], color=INK, zorder=3, s=40,
               label=f"Ngưỡng {test['threshold']:.4f}")
    a1.set_xlabel("1 − Specificity (tỷ lệ báo động nhầm)")
    a1.set_ylabel("Sensitivity")
    a1.set_title("Đường ROC (ác tính là lớp dương)")
    a1.legend(loc="lower right")
    base = y_pos.mean()
    a2.plot(rec, prec, color=ACCENT, lw=2, label=f"PR-AUC = {test['pr_auc']:.4f}")
    a2.axhline(base, color="#ADB5BD", lw=1, ls="--", label=f"Tỷ lệ ác tính = {base:.3f}")
    a2.scatter([test["sensitivity"]], [test["precision_malignant"]], color=INK, zorder=3, s=40,
               label=f"Ngưỡng {test['threshold']:.4f}")
    a2.set_xlabel("Recall (sensitivity)")
    a2.set_ylabel("Precision ác tính")
    a2.set_title("Đường Precision–Recall")
    a2.legend(loc="lower left")
    return save(fig, "09_roc_pr.png")


def reliability(report, y_test, proba) -> str:
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    ax.plot([0, 1], [0, 1], color="#ADB5BD", lw=1, ls="--", label="Hiệu chỉnh hoàn hảo")
    y_oof = np.array(report["oof"]["y_true"])
    p_oof = np.array(report["oof"]["proba_malignant"])
    for yy, pp, label, color, marker in ((y_oof, p_oof, "Train (out-of-fold)", "#B197C7", "s"),
                                          (y_test, proba, "Test", ACCENT, "o")):
        frac, mean = calibration_curve((yy == 0).astype(int), pp, n_bins=8, strategy="quantile")
        ax.plot(mean, frac, marker=marker, color=color, lw=1.8, label=label)
    ax.set_xlabel("P(ác tính) dự đoán (trung bình mỗi nhóm)")
    ax.set_ylabel("Tỷ lệ ác tính thực tế")
    ax.set_title("Đường hiệu chỉnh (reliability)")
    ax.legend(loc="upper left")
    return save(fig, "10_hieu_chinh.png")


def probability_hist(y_test, proba, thr) -> str:
    fig, ax = plt.subplots(figsize=(7.2, 4))
    bins = np.linspace(0, 1, 26)
    for cls in (1, 0):
        ax.hist(proba[y_test == cls], bins=bins, alpha=0.7, color=CLASS_COLORS[cls], label=CLASS_VI[cls])
    ax.axvline(thr, color=ACCENT, lw=1.8, ls="--", label=f"Ngưỡng {thr:.4f}")
    ax.set_xlabel("P(ác tính)")
    ax.set_ylabel("Số mẫu test")
    ax.set_title("Phân phối xác suất ác tính trên tập test, theo nhãn thật")
    ax.legend()
    return save(fig, "11_phan_phoi_xac_suat.png")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = json.loads(TRAIN_REPORT_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    model = joblib.load(MODEL_PATH)

    X, y, names, _ = load_data()
    _, X_test, _, y_test = split(X, y)
    proba = malignant_proba(model, X_test)
    thr = metadata["threshold_malignant"]
    test = clinical_metrics(y_test, proba, thr)
    test_half = clinical_metrics(y_test, proba, 0.5)
    if test["sensitivity"] != report["metrics"]["test"]["sensitivity"]:
        raise SystemExit("Artifact không khớp train_report.json — hãy chạy lại scripts/train.py")

    errors = [
        {"index": int(i), "true": "malignant" if y_test[i] == 0 else "benign",
         "predicted": "malignant" if proba[i] >= thr else "benign", "proba_malignant": round(float(proba[i]), 4)}
        for i in range(len(y_test)) if (proba[i] >= thr) != (y_test[i] == 0)
    ]

    figures = [class_balance(y), feature_distributions(X, y, names), correlation(X, names)]
    pca_name, pca_ev = pca_plot(X, y)
    figures += [pca_name, grid_heatmap(report), calibration_comparison(report), threshold_curve(report),
                confusion(test), roc_pr(y_test, proba, test), reliability(report, y_test, proba),
                probability_hist(y_test, proba, thr)]

    out = {
        "generated_at": report["generated_at"],
        "model": {k: metadata[k] for k in ("model_name", "model_version", "best_params", "calibration",
                                           "threshold_malignant", "target_sensitivity", "sklearn_version")},
        "environment": report["environment"],
        "data": report["data"],
        "grid_search": {k: v for k, v in report["grid_search"].items() if k != "results"},
        "grid_results": report["grid_search"]["results"],
        "calibration": report["calibration"],
        "threshold": report["threshold"],
        "metrics": {"train": report["metrics"]["train"], "cv_oof": report["metrics"]["cv_oof"],
                    "cv_oof_at_0_5": report["metrics"]["cv_oof_at_0_5"], "test": test, "test_at_0_5": test_half},
        "test_errors": errors,
        "pca_explained_variance": [round(v, 4) for v in pca_ev],
        "figures": figures,
    }
    METRICS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[evaluate] test: sensitivity {test['sensitivity']:.4f}, specificity {test['specificity']:.4f}, "
          f"ROC-AUC {test['roc_auc']:.4f}, PR-AUC {test['pr_auc']:.4f}, Brier {test['brier']:.4f}")
    print(f"[evaluate] {len(errors)} mẫu test sai: " + ", ".join(
        f"#{e['index']} {e['true']}→{e['predicted']} (p={e['proba_malignant']})" for e in errors))
    print(f"[evaluate] đã ghi {METRICS_PATH.relative_to(ROOT)} và {len(figures)} hình trong "
          f"{FIG_DIR.relative_to(ROOT)}")
    for doc in MARKDOWN_WITH_METRICS:
        if update_markdown(doc, metrics_table(out)):
            print(f"[evaluate] đã cập nhật bảng số liệu trong {doc.relative_to(ROOT)}")
    if COMPARISON_PATH.exists() and update_markdown(
            ROOT / "README.md", comparison_table(json.loads(COMPARISON_PATH.read_text(encoding="utf-8"))),
            COMPARISON_MARKERS):
        print("[evaluate] đã cập nhật bảng so sánh 5 mô hình trong README.md")


MARKDOWN_WITH_METRICS = [ROOT / "README.md", ROOT / "docs" / "model-card.md"]
START, END = "<!-- metrics:start -->", "<!-- metrics:end -->"
COMPARISON_PATH = REPORT_DIR / "comparison.json"
COMPARISON_MARKERS = ("<!-- comparison:start -->", "<!-- comparison:end -->")


def comparison_table(report: dict) -> str:
    """Markdown table of the five-classifier comparison (reports/comparison.json)."""

    def f(v: float) -> str:
        return f"{v:.4f}".replace(".", ",")

    rows = sorted(report["models"], key=lambda m: (-m["cv_mean"], -m["roc_auc"]))
    lines = [
        f"_Sinh tự động từ `reports/comparison.json` (train lúc {report['trained_at']}). Ngưỡng mỗi mô hình chọn cho "
        f"sensitivity out-of-fold ≥ {f(report['target_sensitivity'])[:4]}; xếp theo CV recall_macro._",
        "",
        "| Mô hình | CV recall_macro | Sensitivity | Specificity | ROC-AUC | Ngưỡng | FN / FP "
        "| Train (ms) | Predict (µs/mẫu) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in rows:
        name = f"**{m['label']}**" if m["model"] == report["best_model"] else m["label"]
        train_ms = f"{m['train_seconds'] * 1000:.1f}".replace(".", ",")
        predict_us = f"{m['predict_ms_per_sample'] * 1000:.1f}".replace(".", ",")
        lines.append(f"| {name} | {f(m['cv_mean'])} ± {f(m['cv_std'])} | {f(m['sensitivity'])} | "
                     f"{f(m['specificity'])} | {f(m['roc_auc'])} | {f(m['threshold'])} | "
                     f"{m['false_negatives']} / {m['false_positives']} | {train_ms} | {predict_us} |")
    return "\n".join(lines)


def metrics_table(out: dict) -> str:
    """Markdown table of the clinical metrics, rewritten on every run so the docs never drift."""
    m = out["metrics"]
    rows = [("Train (fit trên chính tập train)", m["train"]), ("CV out-of-fold (tập train)", m["cv_oof"]),
            ("**Test**", m["test"]), ("Test, ngưỡng mặc định 0,5 (tham khảo)", m["test_at_0_5"])]

    def f(v: float) -> str:
        return f"{v:.4f}".replace(".", ",")

    lines = [
        f"_Sinh tự động bởi `scripts/evaluate.py` từ `reports/metrics.json` (mô hình v{out['model']['model_version']}, "
        f"train lúc {out['generated_at']}). Lớp dương = ác tính._",
        "",
        "| Tập | Ngưỡng | Sensitivity | Specificity | Precision ác tính | F1 ác tính "
        "| ROC-AUC | PR-AUC | Brier | FN | FP |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, x in rows:
        lines.append(f"| {name} | {f(x['threshold'])} | {f(x['sensitivity'])} | {f(x['specificity'])} | "
                     f"{f(x['precision_malignant'])} | {f(x['f1_malignant'])} | {f(x['roc_auc'])} | {f(x['pr_auc'])} | "
                     f"{f(x['brier'])} | {x['false_negatives']} | {x['false_positives']} |")
    return "\n".join(lines)


def update_markdown(path: Path, table: str, markers: tuple[str, str] = (START, END)) -> bool:
    start, end = markers
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if start not in text or end not in text:
        return False
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    path.write_text(f"{head}{start}\n{table}\n{end}{tail}", encoding="utf-8")
    return True


if __name__ == "__main__":
    main()
