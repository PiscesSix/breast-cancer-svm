"""Sinh metrics_data.tex từ reports/metrics.json và artifacts/metadata.json.

Mọi con số trong tài liệu và slide đều là macro sinh ở đây — không chép tay. Huấn luyện lại
(scripts/train.py → scripts/evaluate.py) rồi chạy script này là báo cáo tự cập nhật.

Chạy:  python docs/latex/make_tex_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parents[1]
METRICS = ROOT / "reports" / "metrics.json"
METADATA = ROOT / "artifacts" / "metadata.json"
OUT = DOCS / "metrics_data.tex"
COMPARISON = ROOT / "reports" / "comparison.json"

LABEL_VI = {"malignant": "ác tính", "benign": "lành tính"}
CALIB_NOTE = {
    "svc_probability": "Platt trong libsvm, deprecated từ 1.9",
    "calibrated_sigmoid_single": "khuyến nghị thay \\texttt{probability=True}",
    "calibrated_sigmoid": "trung bình 5 mô hình đã hiệu chỉnh",
    "calibrated_isotonic": "hồi quy đơn điệu, không tham số",
}


def macro(name: str, value) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}"


def tt(text: str) -> str:
    return "\\texttt{" + str(text).replace("_", "\\_") + "}"


def pct(x: float, digits: int = 2) -> str:
    return f"{x * 100:.{digits}f}\\%"


def f4(x: float) -> str:
    return f"{x:.4f}"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    m = json.loads(METRICS.read_text(encoding="utf-8"))
    meta = json.loads(METADATA.read_text(encoding="utf-8"))
    data, grid, calib, thr = m["data"], m["grid_search"], m["calibration"], m["threshold"]
    train, cv, test = m["metrics"]["train"], m["metrics"]["cv_oof"], m["metrics"]["test"]
    test_half, cv_half = m["metrics"]["test_at_0_5"], m["metrics"]["cv_oof_at_0_5"]
    by_method = {c["method"]: c for c in calib["candidates"]}
    chosen = by_method[calib["chosen"]]
    errors = m["test_errors"]
    fps = [e for e in errors if e["predicted"] == "malignant"]
    fns = [e for e in errors if e["predicted"] == "benign"]
    upper_factor = round(meta["features"][0]["upper_bound"] / meta["features"][0]["train_max"])

    lines = [
        "% Tệp sinh tự động bởi docs/latex/make_tex_data.py — KHÔNG sửa tay.",
        f"% Nguồn: reports/metrics.json + artifacts/metadata.json (train lúc {m['generated_at']})",
        "",
        macro("GeneratedAt", m["generated_at"].replace("+00:00", " UTC").replace("T", " ")),
        macro("ModelName", tt(meta["model_name"])),
        macro("ModelVersion", meta["model_version"]),
        macro("SklearnVersion", m["environment"]["scikit_learn"]),
        macro("NumpyVersion", m["environment"]["numpy"]),
        macro("PythonVersion", m["environment"]["python"]),
        macro("DataHashShort", meta["data_hash"][:12]),
        # data
        macro("NSamples", data["n_samples"]),
        macro("NFeatures", data["n_features"]),
        macro("NMalignant", data["n_malignant"]),
        macro("NBenign", data["n_benign"]),
        macro("PctMalignant", pct(data["n_malignant"] / data["n_samples"], 1)),
        macro("PctBenign", pct(data["n_benign"] / data["n_samples"], 1)),
        macro("NTrain", data["n_train"]),
        macro("NTest", data["n_test"]),
        macro("TestMalignant", data["test_malignant"]),
        macro("TestBenign", data["test_benign"]),
        macro("NZeroRows", data["n_zero_rows"]),
        macro("NZeroFeatures", len(data["zero_features"])),
        macro("ZeroFeatures", ", ".join(tt(f) for f in data["zero_features"])),
        macro("RandomState", meta["random_state"]),
        macro("UpperFactor", upper_factor),
        macro("PcaOne", pct(m["pca_explained_variance"][0], 1)),
        macro("PcaTwo", pct(m["pca_explained_variance"][1], 1)),
        macro("PcaTotal", pct(sum(m["pca_explained_variance"]), 1)),
        # grid search
        macro("GridConfigs", grid["n_configs"]),
        macro("GridSeconds", f"{grid['seconds']:.1f}"),
        macro("GridScoring", tt(grid["scoring"])),
        macro("BestC", grid["best_params"]["svc__C"]),
        macro("BestGamma", grid["best_params"]["svc__gamma"]),
        macro("GridCVMean", f4(grid["cv_mean"])),
        macro("GridCVStd", f4(grid["cv_std"])),
        # calibration
        macro("CalibChosen", tt(calib["chosen"])),
        macro("CalibChosenBrier", f"{chosen['brier']:.5f}"),
        macro("CalibBaselineBrier", f"{by_method['svc_probability']['brier']:.5f}"),
        macro("CalibSigmoidBrier", f"{by_method['calibrated_sigmoid']['brier']:.5f}"),
        macro("CalibIsotonicBrier", f"{by_method['calibrated_isotonic']['brier']:.5f}"),
        # threshold
        macro("Threshold", f4(thr["value"])),
        macro("TargetSens", f"{thr['target_sensitivity']:.2f}"),
        # A threshold t is optimal when missing a malignant case costs (1 - t) / t times a false alarm.
        macro("ImpliedCostRatio", f"{(1 - thr['value']) / thr['value']:.2f}"),
        # metrics
        macro("TrainSens", f4(train["sensitivity"])), macro("TrainSpec", f4(train["specificity"])),
        macro("CVSens", f4(cv["sensitivity"])), macro("CVSpec", f4(cv["specificity"])),
        macro("CVTP", cv["confusion_matrix"][0][0]), macro("CVFN", cv["false_negatives"]),
        macro("CVFP", cv["false_positives"]),
        macro("CVHalfSens", f4(cv_half["sensitivity"])), macro("CVHalfSpec", f4(cv_half["specificity"])),
        macro("CVHalfTP", cv_half["confusion_matrix"][0][0]), macro("CVHalfFN", cv_half["false_negatives"]),
        macro("CVHalfFP", cv_half["false_positives"]),
        macro("CVMalignant", cv["confusion_matrix"][0][0] + cv["false_negatives"]),
        macro("TestSens", f4(test["sensitivity"])), macro("TestSpec", f4(test["specificity"])),
        macro("TestPrec", f4(test["precision_malignant"])), macro("TestFOne", f4(test["f1_malignant"])),
        macro("TestNPV", f4(test["npv"])), macro("TestAcc", f4(test["accuracy"])),
        macro("TestAUC", f4(test["roc_auc"])), macro("TestPRAUC", f4(test["pr_auc"])),
        macro("TestBrier", f4(test["brier"])),
        macro("TestTP", test["confusion_matrix"][0][0]), macro("TestFN", test["confusion_matrix"][0][1]),
        macro("TestFP", test["confusion_matrix"][1][0]), macro("TestTN", test["confusion_matrix"][1][1]),
        macro("HalfSens", f4(test_half["sensitivity"])), macro("HalfSpec", f4(test_half["specificity"])),
        macro("HalfPrec", f4(test_half["precision_malignant"])),
        macro("HalfFN", test_half["false_negatives"]), macro("HalfFP", test_half["false_positives"]),
        macro("TestNErrors", len(errors)),
        macro("MissedProba", ", ".join(f"{e['proba_malignant']:.4f}" for e in fns) or "---"),
        macro("FPMinProba", f"{min(e['proba_malignant'] for e in fps):.4f}" if fps else "---"),
        macro("FPMaxProba", f"{max(e['proba_malignant'] for e in fps):.4f}" if fps else "---"),
        macro("FPBelowHalf", sum(e["proba_malignant"] < 0.5 for e in fps)),
        "",
        "% Bảng so sánh cách hiệu chỉnh xác suất (4 cột)",
        r"\newcommand{\CalibRows}{%",
    ]
    for c in calib["candidates"]:
        name = tt(c["method"])
        if c["method"] == calib["chosen"]:
            name = "\\textbf{" + name + "}"
        lines.append(f"  {name} & {c['brier']:.5f} & {c['log_loss']:.5f} & {c['roc_auc']:.4f} & "
                     f"{CALIB_NOTE.get(c['method'], '')} \\\\")
    lines += ["}", "", "% Bảng metric train / CV / test (10 cột)", r"\newcommand{\MetricRows}{%"]
    for label, x in (("Train", train), ("CV out-of-fold", cv), ("\\textbf{Test}", test),
                     ("Test, ngưỡng 0.5", test_half)):
        lines.append(
            f"  {label} & {x['threshold']:.4f} & {f4(x['sensitivity'])} & {f4(x['specificity'])} & "
            f"{f4(x['precision_malignant'])} & {f4(x['f1_malignant'])} & {f4(x['roc_auc'])} & "
            f"{f4(x['pr_auc'])} & {x['false_negatives']} & {x['false_positives']} \\\\")
    lines += ["}", "", "% Bảng metric rút gọn cho slide (6 cột)", r"\newcommand{\MetricRowsShort}{%"]
    for label, x in (("Train", train), ("CV (OOF)", cv), ("\\textbf{Test}", test), ("Test @ 0.5", test_half)):
        lines.append(f"  {label} & {f4(x['sensitivity'])} & {f4(x['specificity'])} & "
                     f"{f4(x['precision_malignant'])} & {f4(x['roc_auc'])} & {x['false_negatives']} \\\\")
    lines += ["}", "", "% Các mẫu test bị dự đoán sai (4 cột)", r"\newcommand{\ErrorRows}{%"]
    for e in errors:
        lines.append(f"  {e['index']} & {LABEL_VI[e['true']]} & {LABEL_VI[e['predicted']]} & "
                     f"{e['proba_malignant']:.4f} \\\\")
    lines += ["}", "", "% Kết quả GridSearchCV (4 cột)", r"\newcommand{\GridRows}{%"]
    for r in sorted(m["grid_results"], key=lambda r: r["rank"]):
        lines.append(f"  {r['C']} & {r['gamma']} & {r['mean']:.4f} $\\pm$ {r['std']:.4f} & {r['rank']} \\\\")
    lines += ["}", ""]
    if COMPARISON.exists():
        lines += comparison_lines(json.loads(COMPARISON.read_text(encoding="utf-8")))

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUT.relative_to(ROOT)} ({len(lines)} dòng)")


def comparison_lines(r: dict) -> list[str]:
    """Macros for the five-classifier comparison (reports/comparison.json)."""
    rows = sorted(r["models"], key=lambda m: (-m["cv_mean"], -m["roc_auc"]))
    by_key = {m["model"]: m for m in r["models"]}
    best, svm = by_key[r["best_model"]], by_key["svm_rbf"]
    fastest = min(r["models"], key=lambda m: m["predict_ms_per_sample"])
    lines = [
        f"% ----- So sánh 5 mô hình phân loại (reports/comparison.json, train lúc {r['trained_at']}) -----",
        macro("CmpNModels", len(r["models"])),
        macro("CmpSeconds", f"{r['total_seconds']:.1f}"),
        macro("CmpBestLabel", best["label"]),
        macro("CmpBestCV", f4(best["cv_mean"])),
        macro("CmpBestCVStd", f4(best["cv_std"])),
        macro("CmpSvmCV", f4(svm["cv_mean"])),
        macro("CmpSvmCVStd", f4(svm["cv_std"])),
        macro("CmpGap", f4(best["cv_mean"] - svm["cv_mean"])),
        macro("CmpBestSpec", f4(best["specificity"])),
        macro("CmpFastestLabel", fastest["label"]),
        macro("CmpFastestUs", f"{fastest['predict_ms_per_sample'] * 1000:.1f}"),
        macro("CmpSpeedFast", f"{r['speed_thresholds']['fast']:g}"),
        macro("CmpSpeedMedium", f"{r['speed_thresholds']['medium']:g}"),
        "",
        "% Bảng so sánh (9 cột), dòng in đậm là mô hình có CV cao nhất",
        r"\newcommand{\CmpRows}{%",
    ]
    for m in rows:
        name = f"\\textbf{{{m['label']}}}" if m["model"] == r["best_model"] else m["label"]
        lines.append(
            f"  {name} & {f4(m['cv_mean'])} & {f4(m['sensitivity'])} & {f4(m['specificity'])} & {f4(m['roc_auc'])} "
            f"& {f4(m['threshold'])} & {m['false_negatives']}/{m['false_positives']} "
            f"& {m['train_seconds'] * 1000:.1f} & {m['predict_ms_per_sample'] * 1000:.1f} \\\\")
    lines += ["}", "", "% Bảng rút gọn cho slide (5 cột)", r"\newcommand{\CmpRowsShort}{%"]
    for m in rows:
        name = f"\\textbf{{{m['label']}}}" if m["model"] == r["best_model"] else m["label"]
        lines.append(f"  {name} & {f4(m['cv_mean'])} & {f4(m['sensitivity'])} & {f4(m['specificity'])} "
                     f"& {f4(m['roc_auc'])} \\\\")
    lines += ["}", ""]
    return lines


if __name__ == "__main__":
    main()
