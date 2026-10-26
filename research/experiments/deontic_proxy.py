"""Reproducible five-class deontic-modality proxy experiment.

Run from the repository root:
    .venv/bin/python -m research.experiments.deontic_proxy

This evaluates provision-level labels from Minkova et al.'s released dataset.
It does not evaluate obligation spans, fields, provenance, or policy comparison.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import urllib.request
from collections import Counter
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
from sklearn.metrics import accuracy_score, f1_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

from backend.engine import ENGINE_VERSION, analyze_document


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".regulatrace" / "experiments" / "original_df.csv"
RESULTS = ROOT / "research" / "experiments" / "results" / "deontic_proxy_results.json"
FIGURES = ROOT / "paper" / "regulatrace-preprint" / "figures"
SOURCE_DOI = "https://doi.org/10.34894/HQ8LIH"
SOURCE_URL = "https://dataverse.nl/api/access/datafile/383750"
SOURCE_SHA256 = "706cd28fad74b126d3dc1ad56cf86e0f520eb7fce6defa00a281b45b98ab56af"
LABELS = ["Obligation", "Permission", "Prohibition", "Power", "Right"]
PREDICTION_LABELS = [*LABELS, "ABSTAIN"]
SEED = 42
N_SPLITS = 3
SIMILARITY_THRESHOLD = 0.75


def load_data() -> tuple[np.ndarray, np.ndarray]:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE.exists():
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
            CACHE.write_bytes(response.read())
    digest = hashlib.sha256(CACHE.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"dataset hash mismatch: {digest}")
    with CACHE.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["annotator"] == "A1"]
    deduplicated: dict[str, str] = {}
    for row in rows:
        text = row["text"].strip()
        if text in deduplicated and deduplicated[text] != row["label"]:
            raise ValueError("duplicate A1 text has conflicting labels")
        deduplicated[text] = row["label"]
    texts = np.array(list(deduplicated))
    labels = np.array(list(deduplicated.values()))
    if len(rows) != 567 or len(texts) != 566 or set(labels) != set(LABELS):
        raise ValueError("unexpected A1 sample count, deduplicated count, or labels")
    return texts, labels


def similarity_groups(texts: np.ndarray) -> np.ndarray:
    """Group exact or highly similar texts before train/test fold assignment."""
    vectors = TfidfVectorizer(analyzer="char", ngram_range=(3, 5)).fit_transform(texts)
    similarities = cosine_similarity(vectors)
    parent = list(range(len(texts)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left in range(len(texts)):
        for right in range(left + 1, len(texts)):
            if similarities[left, right] >= SIMILARITY_THRESHOLD:
                parent[find(left)] = find(right)
    return np.array([find(index) for index in range(len(texts))])


def rule_prediction(text: str) -> str:
    records = analyze_document(text)["normative"]
    label = records[0]["modality"] if records else "INFORMATION"
    return {
        "OBLIGATION": "Obligation",
        "PERMISSION": "Permission",
        "PROHIBITION": "Prohibition",
    }.get(label, "ABSTAIN")


def models() -> dict[str, object]:
    return {
        "Majority": DummyClassifier(strategy="most_frequent"),
        "Word TF-IDF + LR": make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=20000, sublinear_tf=True),
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, solver="newton-cg", random_state=SEED),
        ),
        "Word TF-IDF + SVM": make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=20000, sublinear_tf=True),
            LinearSVC(C=1.0, class_weight="balanced", random_state=SEED),
        ),
        "Char TF-IDF + SVM": make_pipeline(
            TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2, max_features=50000, sublinear_tf=True),
            LinearSVC(C=1.0, class_weight="balanced", random_state=SEED),
        ),
    }


def plot_scores(report: dict) -> None:
    names = list(report["models"])
    accuracies = [report["models"][name]["accuracy_mean"] for name in names]
    accuracy_sd = [report["models"][name]["accuracy_sd"] for name in names]
    macro = [report["models"][name]["macro_f1_mean"] for name in names]
    macro_sd = [report["models"][name]["macro_f1_sd"] for name in names]
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8.7, 4.2), layout="constrained")
    ax.barh(y - 0.18, accuracies, 0.34, xerr=accuracy_sd, label="Accuracy", color="#167d91", capsize=3)
    ax.barh(y + 0.18, macro, 0.34, xerr=macro_sd, label="Macro F1", color="#ef8b4d", capsize=3)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Mean across 3 grouped folds (error bars: one fold SD)")
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.01, 0.5))
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(FIGURES / "deontic_proxy_scores.png", dpi=220)
    plt.close(fig)

    best = report["best_model_by_macro_f1"]
    matrix = np.array(report["models"][best]["confusion_matrix"])
    proportions = matrix / matrix.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(7.0, 5.4), layout="constrained")
    image = ax.imshow(proportions, cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(range(len(PREDICTION_LABELS)), PREDICTION_LABELS, rotation=35, ha="right")
    ax.set_yticks(range(len(LABELS)), LABELS)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Gold")
    ax.set_title(f"{best}: out-of-fold predictions")
    for row in range(len(LABELS)):
        for col in range(len(PREDICTION_LABELS)):
            value = matrix[row, col]
            ax.text(col, row, str(value), ha="center", va="center", color="white" if proportions[row, col] > 0.5 else "#163047")
    fig.colorbar(image, ax=ax, shrink=0.8, label="Share within gold class")
    fig.savefig(FIGURES / "deontic_proxy_confusion.png", dpi=220)
    plt.close(fig)

    comparator = "Word TF-IDF + LR"
    index = np.arange(len(LABELS))
    rule_f1 = [report["models"]["RegulaTrace rules"]["per_class_f1_oof"][label] for label in LABELS]
    learned_f1 = [report["models"][comparator]["per_class_f1_oof"][label] for label in LABELS]
    fig, ax = plt.subplots(figsize=(8.2, 3.8), layout="constrained")
    ax.bar(index - 0.19, rule_f1, 0.36, label="RegulaTrace rules", color="#167d91")
    ax.bar(index + 0.19, learned_f1, 0.36, label=comparator, color="#ef8b4d")
    ax.set_xticks(index, [f"{label}\n(n={report['class_support'][label]})" for label in LABELS])
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Out-of-fold F1")
    ax.legend(frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(FIGURES / "deontic_proxy_per_class.png", dpi=220)
    plt.close(fig)


def main() -> None:
    texts, gold = load_data()
    groups = similarity_groups(texts)
    folds = list(StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED).split(texts, gold, groups))
    rule = np.array([rule_prediction(text) for text in texts])
    all_models = {"RegulaTrace rules": None, **models()}
    result: dict = {
        "dataset": SOURCE_DOI,
        "dataset_sha256": SOURCE_SHA256,
        "selection": "annotator A1 only; five deontic classes; no unannotated None rows",
        "sample_count": len(texts),
        "class_support": dict(Counter(gold)),
        "split": f"{N_SPLITS}-fold StratifiedGroupKFold, seed {SEED}; char 3-5gram TF-IDF cosine >= {SIMILARITY_THRESHOLD} grouped",
        "similarity_group_count": len(set(groups)),
        "task_scope": "provision-level modality only; not span or field extraction",
        "versions": {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                     "numpy": np.__version__, "scipy": scipy.__version__,
                     "matplotlib": matplotlib.__version__, "regulatrace_engine": ENGINE_VERSION},
        "models": {},
    }
    for name, model in all_models.items():
        out_of_fold = np.full(len(gold), "", dtype="<U32")
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
                "accuracy": float(accuracy_score(gold[test_index], predictions)),
                "macro_f1": float(f1_score(gold[test_index], predictions, labels=LABELS, average="macro", zero_division=0)),
            })
        accuracy = [fold["accuracy"] for fold in fold_scores]
        macro = [fold["macro_f1"] for fold in fold_scores]
        result["models"][name] = {
            "folds": fold_scores,
            "accuracy_mean": float(np.mean(accuracy)),
            "accuracy_sd": float(np.std(accuracy, ddof=1)),
            "macro_f1_mean": float(np.mean(macro)),
            "macro_f1_sd": float(np.std(macro, ddof=1)),
            "accuracy_oof": float(accuracy_score(gold, out_of_fold)),
            "macro_f1_oof": float(f1_score(gold, out_of_fold, labels=LABELS, average="macro", zero_division=0)),
            "per_class_f1_oof": {label: float(f1_score(gold, out_of_fold, labels=[label], average="macro", zero_division=0)) for label in LABELS},
            "confusion_matrix": [[int(sum((gold == true) & (out_of_fold == predicted)))
                                  for predicted in PREDICTION_LABELS] for true in LABELS],
            "confusion_columns": PREDICTION_LABELS,
            "abstentions": int(sum(out_of_fold == "ABSTAIN")),
        }
    result["best_model_by_macro_f1"] = max(result["models"], key=lambda name: result["models"][name]["macro_f1_mean"])
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    plot_scores(result)
    print(json.dumps({"samples": len(texts), "groups": len(set(groups)), "best": result["best_model_by_macro_f1"],
                      "scores": {name: {key: value[key] for key in ("accuracy_mean", "macro_f1_mean", "accuracy_sd", "macro_f1_sd", "abstentions")}
                                 for name, value in result["models"].items()}}, indent=2))


if __name__ == "__main__":
    main()
