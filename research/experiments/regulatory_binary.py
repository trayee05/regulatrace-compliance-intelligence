"""Source-grouped regulatory-statement classification on an external EU dataset.

Run from the repository root:
    .venv/bin/python -m research.experiments.regulatory_binary

The binary label is regulatory versus constitutive statement, not full
obligation extraction or legal correctness.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

from backend.engine import ENGINE_VERSION, analyze_document


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".regulatrace" / "experiments" / "complete_training_data.csv"
RESULTS = ROOT / "research" / "experiments" / "results" / "regulatory_binary_results.json"
FIGURES = ROOT / "paper" / "regulatrace-preprint" / "figures"
SOURCE_DOI = "https://doi.org/10.5281/zenodo.8200001"
SOURCE_URL = "https://zenodo.org/records/8200001/files/complete_training_data.csv?download=1"
SOURCE_SHA256 = "510468c8eb682a4b6f98984a7221a0a157e9a323c4893a0d49723acfa2b16238"
LABEL_COLUMN = "Regulatory (1) Constitutive (0)"
SEED = 42
N_SPLITS = 3


def load_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE.exists():
        with urllib.request.urlopen(SOURCE_URL, timeout=90) as response:
            CACHE.write_bytes(response.read())
    digest = hashlib.sha256(CACHE.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"dataset hash mismatch: {digest}")
    with CACHE.open(encoding="utf-8-sig", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))
    by_text: dict[str, list[dict]] = defaultdict(list)
    for row in raw_rows:
        if row["celex"].strip() and row["sent"].strip() and row[LABEL_COLUMN] in {"0.0", "1.0"}:
            normalized = re.sub(r"\s+", " ", row["sent"]).strip()
            by_text[normalized].append(row)
    discordant = 0
    selected = []
    for text, rows in by_text.items():
        labels = {row[LABEL_COLUMN] for row in rows}
        if len(labels) > 1:
            discordant += 1
            continue
        selected.append((text, int(float(rows[0][LABEL_COLUMN])), rows[0]["celex"]))
    texts = np.array([row[0] for row in selected])
    labels = np.array([row[1] for row in selected])
    sources = np.array([row[2] for row in selected])
    if len(raw_rows) != 7240 or len(texts) != 5831 or discordant != 269:
        raise ValueError("unexpected raw, retained, or discordant text count")
    audit = {
        "raw_rows": len(raw_rows),
        "unique_texts_after_deduplication": len(texts),
        "discordant_text_groups_excluded": discordant,
        "source_count": len(set(sources)),
        "class_support": {"constitutive": int(sum(labels == 0)), "regulatory": int(sum(labels == 1))},
        "shall_count": int(sum(bool(re.search(r"\bshall\b", text, re.I)) for text in texts)),
    }
    return texts, labels, sources, audit


def rule_prediction(text: str) -> int:
    return int(bool(analyze_document(text)["normative"]))


def models() -> dict[str, object]:
    return {
        "Majority": DummyClassifier(strategy="most_frequent"),
        "Word TF-IDF + LR": make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=30000, sublinear_tf=True),
            LogisticRegression(C=1.0, max_iter=2000, solver="newton-cg", random_state=SEED),
        ),
        "Word TF-IDF + SVM": make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=30000, sublinear_tf=True),
            LinearSVC(C=1.0, random_state=SEED),
        ),
        "Char TF-IDF + SVM": make_pipeline(
            TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=3, max_features=60000, sublinear_tf=True),
            LinearSVC(C=1.0, random_state=SEED),
        ),
    }


def plot_results(report: dict) -> None:
    names = list(report["models"])
    x = np.arange(len(names))
    accuracy = [report["models"][name]["accuracy_mean"] for name in names]
    accuracy_sd = [report["models"][name]["accuracy_sd"] for name in names]
    f1 = [report["models"][name]["regulatory_f1_mean"] for name in names]
    f1_sd = [report["models"][name]["regulatory_f1_sd"] for name in names]
    fig, ax = plt.subplots(figsize=(9.0, 4.2), layout="constrained")
    ax.bar(x - 0.19, accuracy, 0.36, yerr=accuracy_sd, label="Accuracy", color="#167d91", capsize=3)
    ax.bar(x + 0.19, f1, 0.36, yerr=f1_sd, label="Regulatory F1", color="#ef8b4d", capsize=3)
    ax.set_xticks(x, [name.replace(" + ", "\n+ ") for name in names])
    ax.set_ylim(0, 1.03)
    ax.set_ylabel("Mean across 3 CELEX-grouped folds")
    ax.legend(frameon=False, loc="upper left", ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(FIGURES / "regulatory_binary_scores.png", dpi=220)
    plt.close(fig)

    best = report["best_learned_by_regulatory_f1"]
    choices = ["RegulaTrace rules", best]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.1), layout="constrained")
    for ax, name in zip(axes, choices):
        matrix = np.array(report["models"][name]["confusion_matrix"])
        fractions = matrix / matrix.sum(axis=1, keepdims=True)
        ax.imshow(fractions, cmap="YlGnBu", vmin=0, vmax=1)
        ax.set_xticks([0, 1], ["Constitutive", "Regulatory"], rotation=20, ha="right")
        ax.set_yticks([0, 1], ["Constitutive", "Regulatory"])
        ax.set_title(name)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Gold")
        for row in (0, 1):
            for col in (0, 1):
                ax.text(col, row, str(matrix[row, col]), ha="center", va="center", fontsize=13,
                        color="white" if fractions[row, col] > 0.5 else "#163047")
    fig.savefig(FIGURES / "regulatory_binary_confusion.png", dpi=220)
    plt.close(fig)


def main() -> None:
    texts, gold, sources, audit = load_data()
    folds = list(StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED).split(texts, gold, sources))
    rule = np.array([rule_prediction(text) for text in texts])
    report: dict = {
        "dataset": SOURCE_DOI,
        "dataset_sha256": SOURCE_SHA256,
        "task_scope": "sentence-level regulatory versus constitutive statement; any RegulaTrace normative output mapped to regulatory",
        "cleaning": "normalize whitespace, deduplicate exact text, exclude text with discordant labels, group folds by CELEX",
        "audit": audit,
        "split": f"{N_SPLITS}-fold StratifiedGroupKFold by CELEX, seed {SEED}",
        "versions": {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                     "numpy": np.__version__, "scipy": scipy.__version__,
                     "matplotlib": matplotlib.__version__, "regulatrace_engine": ENGINE_VERSION},
        "models": {},
    }
    for name, model in {"RegulaTrace rules": None, **models()}.items():
        out_of_fold = np.full(len(gold), -1, dtype=int)
        fold_scores = []
        for train_index, test_index in folds:
            if model is None:
                predictions = rule[test_index]
            else:
                model.fit(texts[train_index], gold[train_index])
                predictions = model.predict(texts[test_index])
            out_of_fold[test_index] = predictions
            fold_scores.append({
                "n": len(test_index),
                "regulatory_support": int(sum(gold[test_index] == 1)),
                "accuracy": float(accuracy_score(gold[test_index], predictions)),
                "regulatory_precision": float(precision_score(gold[test_index], predictions, zero_division=0)),
                "regulatory_recall": float(recall_score(gold[test_index], predictions, zero_division=0)),
                "regulatory_f1": float(f1_score(gold[test_index], predictions, zero_division=0)),
            })
        def mean_sd(key: str) -> tuple[float, float]:
            values = [fold[key] for fold in fold_scores]
            return float(np.mean(values)), float(np.std(values, ddof=1))
        accuracy_mean, accuracy_sd = mean_sd("accuracy")
        f1_mean, f1_sd = mean_sd("regulatory_f1")
        report["models"][name] = {
            "folds": fold_scores,
            "accuracy_mean": accuracy_mean,
            "accuracy_sd": accuracy_sd,
            "regulatory_f1_mean": f1_mean,
            "regulatory_f1_sd": f1_sd,
            "accuracy_oof": float(accuracy_score(gold, out_of_fold)),
            "regulatory_precision_oof": float(precision_score(gold, out_of_fold, zero_division=0)),
            "regulatory_recall_oof": float(recall_score(gold, out_of_fold, zero_division=0)),
            "regulatory_f1_oof": float(f1_score(gold, out_of_fold, zero_division=0)),
            "confusion_matrix": confusion_matrix(gold, out_of_fold, labels=[0, 1]).tolist(),
        }
    report["best_learned_by_regulatory_f1"] = max((name for name in report["models"] if name not in {"RegulaTrace rules", "Majority"}),
                                                   key=lambda name: report["models"][name]["regulatory_f1_mean"])
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    plot_results(report)
    print(json.dumps({"audit": audit, "best_learned": report["best_learned_by_regulatory_f1"],
                      "scores": {name: {key: value[key] for key in ("accuracy_mean", "accuracy_sd", "regulatory_f1_mean", "regulatory_f1_sd", "regulatory_precision_oof", "regulatory_recall_oof")}
                                 for name, value in report["models"].items()}}, indent=2))


if __name__ == "__main__":
    main()
