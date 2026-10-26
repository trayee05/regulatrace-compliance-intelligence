"""Evaluate obligation detection on independently annotated JSONL documents.

Usage: python -m research.evaluate path/to/gold.jsonl --split test
The dataset format and annotation rules are documented in PROTOCOL.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from backend.engine import ENGINE_VERSION, analyze_document

SPLITS = {"train", "dev", "test"}
MODALITIES = {"OBLIGATION", "PROHIBITION", "RECOMMENDATION", "PERMISSION"}


def load_gold(path: Path) -> list[dict[str, Any]]:
    """Validate source offsets and reject document or source leakage across splits."""
    documents: list[dict[str, Any]] = []
    ids: set[str] = set()
    source_splits: dict[str, str] = {}
    text_splits: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            document = json.loads(line)
            document_id = document["document_id"]
            source_id = document["source_id"]
            split = document["split"]
            source_text = document["text"]
            annotations = document["annotations"]
            if not all(isinstance(value, str) and value.strip() for value in (document_id, source_id, source_text)):
                raise ValueError("document_id, source_id and text must be nonempty strings")
            if split not in SPLITS or not isinstance(annotations, list):
                raise ValueError("split or annotations is invalid")
            if document_id in ids:
                raise ValueError(f"duplicate document_id {document_id}")
            ids.add(document_id)
            normalized = re.sub(r"\s+", " ", source_text).strip()
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if source_id in source_splits and source_splits[source_id] != split:
                raise ValueError(f"source_id {source_id} crosses splits")
            if digest in text_splits and text_splits[digest] != split:
                raise ValueError("duplicate text crosses splits")
            source_splits[source_id] = split
            text_splits[digest] = split
            annotated_spans: list[tuple[int, int]] = []
            for annotation in annotations:
                start, end = annotation["start"], annotation["end"]
                if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or not 0 <= start < end <= len(source_text):
                    raise ValueError("annotation offsets must be valid Unicode code-point positions")
                if annotation["modality"] not in MODALITIES or not isinstance(annotation["critical"], bool):
                    raise ValueError("annotation modality or critical label is invalid")
                if any(start < previous_end and previous_start < end for previous_start, previous_end in annotated_spans):
                    raise ValueError("gold annotations must not overlap")
                annotated_spans.append((start, end))
            documents.append(document)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    if not documents:
        raise ValueError(f"{path}: no documents found")
    return documents


def _overlap(left: dict[str, int], right: dict[str, int]) -> float:
    intersection = max(0, min(left["end"], right["end"]) - max(left["start"], right["start"]))
    union = max(left["end"], right["end"]) - min(left["start"], right["start"])
    return intersection / union if union else 0.0


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def evaluate(documents: list[dict[str, Any]], split: str = "test", minimum_overlap: float = 0.5) -> dict[str, Any]:
    if split not in SPLITS or not 0 < minimum_overlap <= 1:
        raise ValueError("split or minimum_overlap is invalid")
    selected = [document for document in documents if document["split"] == split]
    if not selected:
        raise ValueError(f"no documents in {split} split")
    dataset_sha256 = hashlib.sha256(json.dumps(sorted(selected, key=lambda document: document["document_id"]), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    true_positive = false_positive = false_negative = modality_correct = critical_total = critical_missed = invalid_provenance = 0
    prediction_count = 0
    errors: list[dict[str, Any]] = []
    for document in selected:
        text = document["text"]
        gold = document["annotations"]
        predictions = analyze_document(text, {"sourceId": document["source_id"]})["normative"]
        prediction_count += len(predictions)
        pairs = sorted(
            ((_overlap(annotation, prediction["sourceSpan"]), gi, pi)
             for gi, annotation in enumerate(gold)
             for pi, prediction in enumerate(predictions) if prediction["sourceSpan"] is not None),
            reverse=True,
        )
        matched_gold: set[int] = set()
        matched_pred: set[int] = set()
        correct_modality_gold: set[int] = set()
        for overlap, gold_index, pred_index in pairs:
            if overlap < minimum_overlap or gold_index in matched_gold or pred_index in matched_pred:
                continue
            matched_gold.add(gold_index)
            matched_pred.add(pred_index)
            true_positive += 1
            expected = gold[gold_index]["modality"]
            observed = predictions[pred_index]["modality"]
            if expected == observed:
                modality_correct += 1
                correct_modality_gold.add(gold_index)
            else:
                errors.append({"document_id": document["document_id"], "type": "wrong_modality", "gold_index": gold_index, "expected": expected, "observed": observed})
        for gold_index, annotation in enumerate(gold):
            if annotation["critical"]:
                critical_total += 1
                if gold_index not in correct_modality_gold:
                    critical_missed += 1
            if gold_index not in matched_gold:
                false_negative += 1
                errors.append({"document_id": document["document_id"], "type": "missed_obligation", "gold_index": gold_index, "start": annotation["start"], "end": annotation["end"], "critical": annotation["critical"]})
        for pred_index, prediction in enumerate(predictions):
            span = prediction["sourceSpan"]
            if pred_index not in matched_pred:
                false_positive += 1
                errors.append({"document_id": document["document_id"], "type": "false_positive", "start": span["start"] if span else None, "end": span["end"] if span else None})
            if span is None or re.sub(r"\s+", " ", text[span["start"]:span["end"]]).strip() != prediction["evidence"]:
                invalid_provenance += 1
                errors.append({"document_id": document["document_id"], "type": "invalid_provenance", "prediction_index": pred_index})
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {
        "split": split,
        "engine_version": ENGINE_VERSION,
        "dataset_sha256": dataset_sha256,
        "document_count": len(selected),
        "gold_obligation_count": sum(len(document["annotations"]) for document in selected),
        "predicted_obligation_count": prediction_count,
        "minimum_overlap": minimum_overlap,
        "candidate_detection": {"tp": true_positive, "fp": false_positive, "fn": false_negative, "precision": precision, "recall": recall, "f1": f1},
        "modality_accuracy_on_matched": _ratio(modality_correct, true_positive),
        "critical_miss_rate": _ratio(critical_missed, critical_total),
        "critical_gold_count": critical_total,
        "invalid_provenance_count": invalid_provenance,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--split", choices=sorted(SPLITS), default="test")
    parser.add_argument("--minimum-overlap", type=float, default=0.5)
    args = parser.parse_args()
    print(json.dumps(evaluate(load_gold(args.dataset), args.split, args.minimum_overlap), indent=2))


if __name__ == "__main__":
    main()
